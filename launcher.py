"""
Gustave Code — Launcher Webapp
Panneau de controle web pour gerer les services Gustave Code.
Aucune dépendance externe — utilise uniquement la stdlib Python.

Le HTML est dans dashboard.html (modifiable à chaud).
Le bouton "Mettre a jour" relance le launcher sans couper les services.

Usage: pythonw.exe launcher.py
       python.exe launcher.py    (debug)
"""

import atexit
import datetime
import http.server
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# -- Redirection stdout/stderr pour pythonw (pas de console) --
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# ============================================================
# Configuration
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
DASHBOARD_HTML = PROJECT_ROOT / "dashboard.html"
CONDA_PYTHON = Path(r"C:\Users\Julien\.conda\envs\llm\python.exe")
OLLAMA_EXE = Path(r"C:\Users\Julien\AppData\Local\Programs\Ollama\ollama.exe")
NPM_CMD = "npm"

LAUNCHER_PORT = 9000
BACKEND_PORT = 8000
CHROMADB_PORT = 8001
FRONTEND_PORT = 3000
OLLAMA_PORT = 11434

MAX_LOG_LINES = 2000

# ============================================================
# Etat global
# ============================================================
processes = {}
is_busy = False
is_updating = False        # True => on relance le launcher, pas de cleanup
server_instance = None

SERVICES = [
    {"id": "ollama",   "name": "Ollama",      "port": OLLAMA_PORT},
    {"id": "chromadb", "name": "ChromaDB",    "port": CHROMADB_PORT},
    {"id": "backend",  "name": "Backend API", "port": BACKEND_PORT},
    {"id": "frontend", "name": "Frontend",    "port": FRONTEND_PORT},
]

# ============================================================
# Système de logs
# ============================================================
log_entries = []
log_counter = 0
log_lock = threading.Lock()

# Anti-répétition : {(service, msg_normalise) -> timestamp}
_recent_msgs = {}
_DEDUP_WINDOW = 10  # secondes


def _normalize_for_dedup(msg):
    """Normalise un message pour la déduplication (supprime chiffres variables)."""
    return re.sub(r'\d+', '#', msg.strip().lower())


# Regex pour stripper les codes ANSI (couleurs, styles) des sorties console
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

# Lignes de bruit verbose à ignorer (debug llama.cpp, GGML, etc.)
# IMPORTANT : on GARDE visible les messages importants :
#   - chargement/déchargement de modèles
#   - allocation GPU/VRAM (inference compute)
#   - démarrage des runners
#   - erreurs de toute sorte
_NOISE_RE = re.compile(r'|'.join([
    # -- llama.cpp debug TRÈS verbose (métadonnées internes) --
    r'^llm_load_print_meta:',     # Dizaines de lignes metadata modèle
    r'^llm_load_tensors:',        # Détails individuels de tenseurs
    r'^llama_model_loader:',      # Détails loader modèle
    r'^llama_kv_cache_',          # Détails cache KV
    r'^load_tensors:',            # Chargement tenseurs (ligne par ligne)
    r'^print_info:',              # Debug llama.cpp
    r'^build_graph:',             # Construction graphe
    r'^common_device_',           # Params device
    r'^system_info:',             # Info système llama.cpp
    r'^sampling\s',               # Params sampling
    r'^CPU\s*\|',                 # Table features CPU
    r'^AVX\s*=',                  # Flags CPU
    r'^General\.architecture',    # Info architecture modèle
    r'^=====',                    # Lignes séparateur
    r'^\.\.\.\s*$',               # Lignes de continuation
    # -- Ollama debug interne Go (pas informatif) --
    r'^runner\.go:\d+',           # Debug runner Go interne
    r'^server\.go:\d+',           # Debug server Go interne
    # -- Ollama startup bruit (pas utile, encombre) --
    r'^time=.*msg="server config"',         # Config dump (très long)
    r'^time=.*msg="Ollama cloud disabled',  # Info cloud
    r'^time=.*msg="total blobs',            # Compteur blobs
    r'^time=.*msg="total unused blobs',     # Blobs inutilisés
    r'^time=.*msg="experimental Vulkan',    # Info Vulkan
    # -- Ollama access logs HTTP (spam massif) --
    r'^\[GIN\]',                            # GIN HTTP access logs
    # -- ChromaDB bruit --
    r'^[\(\)#\s]+$',                        # Lignes du logo ASCII ChromaDB
    r'^Getting started guide:',              # Lien doc ChromaDB
    r'To deploy your DB',                    # Promo Chroma Cloud
    r'^- Sign up:',                          # Promo Chroma Cloud
    r'^- Copy your data',                    # Promo Chroma Cloud
    r'^OpenTelemetry is not enabled',        # Warning OpenTelemetry
]))


def _is_noise(text):
    """Retourne True si la ligne est du bruit verbose à ignorer."""
    stripped = text.strip()
    if not stripped:
        return True
    return bool(_NOISE_RE.match(stripped))


def add_log(service, level, message):
    global log_counter
    if not message or not message.strip():
        return
    msg = message.rstrip()
    if len(msg) > 1000:
        msg = msg[:997] + "..."

    # Anti-répétition : ignorer si meme message du meme service dans les N dernières secondes
    now = time.time()
    dedup_key = (service, _normalize_for_dedup(msg))
    last_time = _recent_msgs.get(dedup_key, 0)
    if now - last_time < _DEDUP_WINDOW:
        return  # Doublon recent, on ignore
    _recent_msgs[dedup_key] = now

    # Nettoyage périodique du dict de dedup (éviter fuite mémoire)
    if len(_recent_msgs) > 500:
        cutoff = now - _DEDUP_WINDOW * 2
        keys_to_del = [k for k, v in _recent_msgs.items() if v < cutoff]
        for k in keys_to_del:
            del _recent_msgs[k]

    with log_lock:
        log_counter += 1
        log_entries.append({
            "id": log_counter,
            "t": datetime.datetime.now().strftime("%H:%M:%S"),
            "svc": service,
            "lvl": level,
            "msg": msg,
        })
        if len(log_entries) > MAX_LOG_LINES:
            del log_entries[:len(log_entries) - MAX_LOG_LINES]


def get_logs_after(after_id):
    with log_lock:
        return [e for e in log_entries if e["id"] > after_id]


def clear_logs():
    global log_counter
    with log_lock:
        log_entries.clear()
        log_counter = 0


def _pipe_reader(service, pipe, level="info"):
    try:
        for raw in iter(pipe.readline, b""):
            try:
                text = raw.decode("utf-8", errors="replace").rstrip()
            except Exception:
                text = repr(raw)
            if not text:
                continue
            # Stripper les codes ANSI (couleurs console) pour des logs propres
            text = _ANSI_RE.sub('', text)
            if not text.strip():
                continue
            lo = text.lower()
            is_err = any(k in lo for k in ("error", "exception", "traceback", "failed", "fatal"))
            # Filtrer le bruit verbose sauf les erreurs
            if not is_err and _is_noise(text):
                continue
            add_log(service, "error" if is_err else level, text)
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def _start_readers(service, proc):
    if proc.stdout:
        threading.Thread(target=_pipe_reader, args=(service, proc.stdout, "info"), daemon=True).start()
    if proc.stderr:
        threading.Thread(target=_pipe_reader, args=(service, proc.stderr, "warn"), daemon=True).start()


# ============================================================
# Utilitaires
# ============================================================

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def kill_process_tree(pid):
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def _kill_all_ollama():
    """Tue TOUS les processus Ollama (serveur, app tray, runners).
    Sur Windows, l'app tray Ollama relance le serveur automatiquement,
    il faut donc aussi tuer l'app tray en premier."""
    # 1. Lister tous les processus contenant 'ollama' dans le nom
    try:
        r = subprocess.run(
            'tasklist | findstr /i "ollama"',
            capture_output=True, text=True, shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        pids = set()
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    if pid > 0:
                        pids.add(pid)
                except (ValueError, IndexError):
                    pass
        # Tuer chaque PID (arbre complet)
        for pid in pids:
            kill_process_tree(pid)
    except Exception:
        pass
    # 2. Fallback: tuer par nom d'executable
    for exe in ["ollama app.exe", "ollama.exe"]:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", exe],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass


def kill_port(port):
    try:
        r = subprocess.run(
            f'netstat -ano | findstr ":{port}" | findstr "LISTENING"',
            capture_output=True, text=True, shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        seen = set()
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if parts:
                pid = int(parts[-1])
                if pid > 0 and pid not in seen:
                    seen.add(pid)
                    kill_process_tree(pid)
    except Exception:
        pass


# ============================================================
# Gestion des services
# ============================================================

def start_service(name):
    if name == "ollama":
        if is_port_in_use(OLLAMA_PORT):
            add_log("launcher", "info", "Ollama déjà actif sur :" + str(OLLAMA_PORT))
            return True
        if not OLLAMA_EXE.exists():
            add_log("launcher", "error", "Ollama introuvable : " + str(OLLAMA_EXE))
            return False
        add_log("launcher", "info", "Démarrage de Ollama...")
        env = os.environ.copy()
        env["OLLAMA_NUM_PARALLEL"] = "1"
        env["OLLAMA_MAX_LOADED_MODELS"] = "1"
        env["OLLAMA_KEEP_ALIVE"] = "30m"
        env["OLLAMA_KV_CACHE_TYPE"] = "q8_0"    # KV cache quantifié (÷2 mémoire, qualité ~identique)
        env["OLLAMA_FLASH_ATTENTION"] = "1"      # Force Flash Attention (réduit VRAM + accélère)
        proc = subprocess.Popen(
            [str(OLLAMA_EXE), "serve"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes["ollama"] = proc
        _start_readers("ollama", proc)
        ok = wait_for_port(OLLAMA_PORT, timeout=15)
        add_log("launcher", "info" if ok else "error",
                "Ollama " + ("OK :" + str(OLLAMA_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    elif name == "chromadb":
        if is_port_in_use(CHROMADB_PORT):
            add_log("launcher", "info", "ChromaDB déjà actif sur :" + str(CHROMADB_PORT))
            return True
        add_log("launcher", "info", "Démarrage de ChromaDB...")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        chroma_exe = CONDA_PYTHON.parent / "Scripts" / "chroma.exe"
        if chroma_exe.exists():
            cmd = [str(chroma_exe), "run", "--host", "0.0.0.0",
                   "--port", str(CHROMADB_PORT),
                   "--path", str(DATA_DIR / "chromadb")]
        else:
            cmd = [str(CONDA_PYTHON), "-m", "chromadb.cli.cli", "run",
                   "--host", "0.0.0.0", "--port", str(CHROMADB_PORT),
                   "--path", str(DATA_DIR / "chromadb")]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT), creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes["chromadb"] = proc
        _start_readers("chromadb", proc)
        ok = wait_for_port(CHROMADB_PORT, timeout=20)
        add_log("launcher", "info" if ok else "error",
                "ChromaDB " + ("OK :" + str(CHROMADB_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    elif name == "backend":
        if is_port_in_use(BACKEND_PORT):
            add_log("launcher", "info", "Backend déjà actif sur :" + str(BACKEND_PORT))
            return True
        add_log("launcher", "info", "Démarrage du Backend API...")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            [str(CONDA_PYTHON), "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(BACKEND_DIR), creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes["backend"] = proc
        _start_readers("backend", proc)
        ok = wait_for_port(BACKEND_PORT, timeout=20)
        add_log("launcher", "info" if ok else "error",
                "Backend " + ("OK :" + str(BACKEND_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    elif name == "frontend":
        if is_port_in_use(FRONTEND_PORT):
            add_log("launcher", "info", "Frontend déjà actif sur :" + str(FRONTEND_PORT))
            return True
        add_log("launcher", "info", "Démarrage du Frontend...")
        env = os.environ.copy()
        env["BROWSER"] = "none"
        env["PORT"] = str(FRONTEND_PORT)
        proc = subprocess.Popen(
            [NPM_CMD, "start"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(FRONTEND_DIR), shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes["frontend"] = proc
        _start_readers("frontend", proc)
        ok = wait_for_port(FRONTEND_PORT, timeout=45)
        add_log("launcher", "info" if ok else "error",
                "Frontend " + ("OK :" + str(FRONTEND_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    return False


def stop_service(name):
    add_log("launcher", "info", "Arrêt de " + name + "...")

    # 1. Tuer le processus qu'on a lance
    proc = processes.pop(name, None)
    if proc and proc.poll() is None:
        kill_process_tree(proc.pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    # 2. Cas special Ollama : tuer l'app tray + serveur + runners
    if name == "ollama":
        _kill_all_ollama()
        # Attendre un peu car l'app tray peut tenter un dernier restart
        time.sleep(2)
        # Si toujours actif, re-tuer (le tray a pu relancer entre-temps)
        if is_port_in_use(OLLAMA_PORT):
            _kill_all_ollama()
            time.sleep(1)
    else:
        # 3. Pour les autres services : kill par port en fallback
        port_map = {
            "chromadb": CHROMADB_PORT,
            "backend": BACKEND_PORT,
            "frontend": FRONTEND_PORT,
        }
        port = port_map.get(name)
        if port and is_port_in_use(port):
            kill_port(port)
            for _ in range(10):
                if not is_port_in_use(port):
                    break
                time.sleep(0.3)

    # 4. Vérification finale
    port_map_all = {
        "ollama": OLLAMA_PORT, "chromadb": CHROMADB_PORT,
        "backend": BACKEND_PORT, "frontend": FRONTEND_PORT,
    }
    port = port_map_all.get(name)
    stopped = not is_port_in_use(port) if port else True
    add_log("launcher", "info" if stopped else "error",
            name + (" arrêté" if stopped else " : port encore occupé"))


def start_all():
    global is_busy
    if is_busy:
        return
    is_busy = True
    add_log("launcher", "info", "=== Démarrage de tous les services ===")
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for svc in SERVICES:
            start_service(svc["id"])
        add_log("launcher", "info", "=== Démarrage terminé ===")
    finally:
        is_busy = False


def stop_all():
    global is_busy
    if is_busy:
        return
    is_busy = True
    add_log("launcher", "info", "=== Arrêt de tous les services ===")
    try:
        for svc in reversed(SERVICES):
            stop_service(svc["id"])
        add_log("launcher", "info", "=== Arrêt terminé ===")
    finally:
        is_busy = False


def reload_all():
    global is_busy
    if is_busy:
        return
    is_busy = True
    add_log("launcher", "info", "=== Rechargement de tous les services ===")
    try:
        for svc in reversed(SERVICES):
            stop_service(svc["id"])
        time.sleep(1)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for svc in SERVICES:
            start_service(svc["id"])
        add_log("launcher", "info", "=== Rechargement terminé ===")
    finally:
        is_busy = False


def get_status():
    statuses = {}
    for svc in SERVICES:
        statuses[svc["id"]] = "running" if is_port_in_use(svc["port"]) else "stopped"
    return {"services": statuses, "busy": is_busy}


# ============================================================
# Nettoyage
# ============================================================

def cleanup():
    if is_updating:
        return  # Pas de cleanup pendant une mise à jour
    # Tuer nos processus
    for name in ["frontend", "backend", "chromadb"]:
        proc = processes.get(name)
        if proc and proc.poll() is None:
            kill_process_tree(proc.pid)
    # Kill par port pour frontend/backend/chromadb
    for port in [FRONTEND_PORT, BACKEND_PORT, CHROMADB_PORT]:
        if is_port_in_use(port):
            kill_port(port)
    # Ollama : traitement special (app tray)
    if is_port_in_use(OLLAMA_PORT):
        _kill_all_ollama()
    proc = processes.get("ollama")
    if proc and proc.poll() is None:
        kill_process_tree(proc.pid)


atexit.register(cleanup)


def _signal_handler(sig, frame):
    _shutdown_server()  # Arrêt propre via le même chemin que le heartbeat

signal.signal(signal.SIGTERM, _signal_handler)
if hasattr(signal, "SIGBREAK"):
    signal.signal(signal.SIGBREAK, _signal_handler)


# ============================================================
# Page HTML (lu depuis dashboard.html)
# ============================================================

def load_dashboard():
    """Lit dashboard.html depuis le disque et injecte les ports.
    Lu à chaque requête => modifications HTML/CSS/JS prises en compte instantanément."""
    try:
        raw = DASHBOARD_HTML.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "<h1>dashboard.html introuvable</h1><p>Fichier attendu : " + str(DASHBOARD_HTML) + "</p>"
    return (raw
        .replace("$OLLAMA_PORT", str(OLLAMA_PORT))
        .replace("$CHROMADB_PORT", str(CHROMADB_PORT))
        .replace("$BACKEND_PORT", str(BACKEND_PORT))
        .replace("$FRONTEND_PORT", str(FRONTEND_PORT))
    )


# Heartbeat : le dashboard envoie un ping toutes les 3s.
# Si plus de heartbeat pendant _HEARTBEAT_TIMEOUT => onglet fermé => shutdown auto.
_heartbeat = {"last": 0.0, "active": False, "started": 0.0}
_HEARTBEAT_TIMEOUT = 30  # secondes sans heartbeat => shutdown
_shutting_down = False


def _find_browser_exe():
    """Trouve l'executable Chrome ou Edge sur Windows."""
    if sys.platform != "win32":
        return None
    candidates = []
    for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env_var, "")
        if base:
            candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    for exe in candidates:
        if exe.exists():
            return str(exe)
    return None


_BROWSER_EXE = _find_browser_exe()


def _open_browser(url, force_new=False):
    """Ouvre l'URL dans le navigateur.
    force_new=True  => nouvelle fenêtre dédiée (premier lancement)
    force_new=False => focalise l'onglet existant (relancement)"""
    if force_new and _BROWSER_EXE:
        try:
            subprocess.Popen(
                [_BROWSER_EXE, "--new-window", url],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return
        except Exception:
            pass
    webbrowser.open(url)


# ============================================================
# Serveur HTTP
# ============================================================

class LauncherHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def _json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, content, status=200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._html(load_dashboard())
        elif path == "/api/status":
            self._json(get_status())
        elif path == "/api/logs":
            qs = parse_qs(urlparse(self.path).query)
            after = int(qs.get("after", ["0"])[0])
            self._json({"logs": get_logs_after(after)})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/start":
            threading.Thread(target=start_all, daemon=True).start()
            self._json({"ok": True})
        elif self.path == "/api/stop":
            threading.Thread(target=stop_all, daemon=True).start()
            self._json({"ok": True})
        elif self.path == "/api/reload":
            threading.Thread(target=reload_all, daemon=True).start()
            self._json({"ok": True})
        elif self.path == "/api/quit":
            self._json({"ok": True})
            threading.Thread(target=_shutdown_server, daemon=True).start()
        elif self.path == "/api/update":
            self._json({"ok": True})
            threading.Thread(target=_restart_launcher, daemon=True).start()
        elif self.path == "/api/heartbeat":
            _heartbeat["last"] = time.time()
            _heartbeat["active"] = True
            self._json({"ok": True})
        elif self.path == "/api/logs/clear":
            clear_logs()
            self._json({"ok": True})
        else:
            self.send_error(404)


def _shutdown_server():
    """Arrêt complet : stoppe tous les services puis le serveur HTTP et le process."""
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True

    # Filet de sécurité : forcer l'arrêt après 30s quoi qu'il arrive
    threading.Timer(30.0, lambda: os._exit(0)).start()

    add_log("launcher", "info", "=== Arrêt de Gustave Code ===")
    time.sleep(0.5)

    # Stopper chaque service (ordre inverse)
    for svc in reversed(SERVICES):
        try:
            stop_service(svc["id"])
        except Exception:
            pass

    add_log("launcher", "info", "=== Tous les services arrêtés ===")
    time.sleep(0.5)

    # Arrêter le serveur HTTP (débloque serve_forever dans main)
    if server_instance:
        try:
            server_instance.shutdown()
        except Exception:
            pass

    # Laisser le finally de main() faire le os._exit(0)
    # Le timer de 30s est la en securite si tout bloque


def _restart_launcher():
    """Relance le processus Python (les services restent actifs)."""
    global is_updating
    is_updating = True
    _heartbeat["active"] = False  # Reset heartbeat pendant la mise a jour
    add_log("launcher", "info", "=== Mise à jour du launcher ===")
    time.sleep(0.5)
    if server_instance:
        server_instance.shutdown()
    # serve_forever() va retourner, et main() va detecter is_updating


def _heartbeat_watchdog():
    """Surveille le heartbeat du dashboard. Onglet fermé => arrêt automatique."""
    while True:
        time.sleep(3)
        if is_updating or _shutting_down:
            continue
        if not _heartbeat["active"]:
            # Aucun dashboard connecté : timeout de sécurité 60s après démarrage
            if _heartbeat["started"] > 0 and time.time() - _heartbeat["started"] > 60:
                add_log("launcher", "info", "Aucun dashboard connecté — arrêt automatique")
                _shutdown_server()
                break
            continue
        elapsed = time.time() - _heartbeat["last"]
        if elapsed > _HEARTBEAT_TIMEOUT:
            add_log("launcher", "info", "Dashboard fermé — arrêt automatique des services")
            _shutdown_server()
            break


# ============================================================
# Point d'entree
# ============================================================

def main():
    global server_instance, is_updating

    if is_port_in_use(LAUNCHER_PORT):
        # Launcher déjà actif => focaliser l'onglet existant
        _open_browser(f"http://localhost:{LAUNCHER_PORT}", force_new=False)
        return

    server_instance = http.server.HTTPServer(
        ("127.0.0.1", LAUNCHER_PORT), LauncherHandler
    )
    add_log("launcher", "info", "Gustave Code Launcher démarré sur :" + str(LAUNCHER_PORT))
    print(f"Gustave Code Launcher -> http://localhost:{LAUNCHER_PORT}")

    # Détection des services déjà actifs au lancement (ex: Ollama tray app Windows)
    for svc in SERVICES:
        if is_port_in_use(svc["port"]):
            add_log("launcher", "info",
                     svc["name"] + " déjà actif (instance externe sur :" + str(svc["port"]) + ")")

    # Heartbeat watchdog : éteint tout si l'onglet dashboard est ferme
    _heartbeat["started"] = time.time()
    threading.Thread(target=_heartbeat_watchdog, daemon=True).start()

    # Premier lancement => ouvrir dans une nouvelle fenêtre dédiée
    threading.Timer(0.8, lambda: _open_browser(
        f"http://localhost:{LAUNCHER_PORT}", force_new=True
    )).start()

    try:
        server_instance.serve_forever()
    except KeyboardInterrupt:
        # Ctrl+C en debug => lancer l'arret propre
        if not _shutting_down:
            _shutdown_server()
    finally:
        if is_updating:
            # Relancer le processus — les services restent vivants
            try:
                server_instance.server_close()
            except Exception:
                pass
            python = sys.executable
            os.execv(python, [python, str(Path(__file__).resolve())])
        else:
            # _shutdown_server() a deja stoppe les services
            # On ferme juste le socket HTTP et on quitte
            try:
                server_instance.server_close()
            except Exception:
                pass
            os._exit(0)


if __name__ == "__main__":
    main()
