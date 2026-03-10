"""
Gustave Code — Launcher natif (PyQt6)
Application desktop native remplaçant le dashboard web.
Gère les 4 services (Ollama, ChromaDB, Backend, Frontend) en subprocess.

Usage: pythonw.exe app.py
       python.exe app.py    (debug)
"""

import atexit
import datetime
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

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QObject, QThread, QPoint,
)
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTextEdit, QMessageBox, QGridLayout,
)


# ============================================================
# Configuration
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
CONDA_PYTHON = Path(r"C:\Users\Julien\.conda\envs\llm\python.exe")
OLLAMA_EXE = Path(r"C:\Users\Julien\AppData\Local\Programs\Ollama\ollama.exe")
NPM_CMD = "npm"

BACKEND_PORT = 8000
CHROMADB_PORT = 8001
FRONTEND_PORT = 3000
OLLAMA_PORT = 11434

SERVICES = [
    {"id": "ollama",   "name": "Ollama",      "port": OLLAMA_PORT},
    {"id": "chromadb", "name": "ChromaDB",    "port": CHROMADB_PORT},
    {"id": "backend",  "name": "Backend API", "port": BACKEND_PORT},
    {"id": "frontend", "name": "Frontend",    "port": FRONTEND_PORT},
]

MAX_LOG_LINES = 1500
WINDOW_WIDTH = 960
LOGS_MIN_HEIGHT = 80
LOGS_MAX_HEIGHT = 350

# Couleurs du thème
C_BG = "#0c0b09"
C_PANEL = "#171411"
C_BORDER = "#332c24"
C_TEXT = "#e4d5be"
C_GOLD = "#c9a84c"
C_MUTED = "#8a7d6b"
C_DIM = "#5a5040"
C_DARK = "#1e1a14"

# Regex bruit (identique à launcher.py)
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
_NOISE_RE = re.compile(r'|'.join([
    r'^llm_load_print_meta:', r'^llm_load_tensors:', r'^llama_model_loader:',
    r'^llama_kv_cache_', r'^load_tensors:', r'^print_info:', r'^build_graph:',
    r'^common_device_', r'^system_info:', r'^sampling\s', r'^CPU\s*\|',
    r'^AVX\s*=', r'^General\.architecture', r'^=====', r'^\.\.\.\s*$',
    r'^runner\.go:\d+', r'^server\.go:\d+',
    r'^time=.*msg="server config"', r'^time=.*msg="Ollama cloud disabled',
    r'^time=.*msg="total blobs', r'^time=.*msg="total unused blobs',
    r'^time=.*msg="experimental Vulkan', r'^\[GIN\]',
    r'^[\(\)#\s]+$', r'^Getting started guide:', r'To deploy your DB',
    r'^- Sign up:', r'^- Copy your data', r'^OpenTelemetry is not enabled',
]))

_DEDUP_WINDOW = 10
_recent_msgs = {}


def _normalize_for_dedup(msg):
    return re.sub(r'\d+', '#', msg.strip().lower())


def _is_noise(text):
    stripped = text.strip()
    return (not stripped) or bool(_NOISE_RE.match(stripped))


# ============================================================
# Signaux Qt (bridge threads → UI)
# ============================================================

class Signals(QObject):
    log_received = pyqtSignal(str, str, str)   # (service, level, message)
    state_changed = pyqtSignal(dict)            # {svc_id: "running"/"stopped"}
    busy_changed = pyqtSignal(bool)             # is_busy changed
    quit_ready = pyqtSignal()                   # services arrêtés → fermer l'app


signals = Signals()


class StatusPoller(QThread):
    """Thread dédié au polling des ports (évite de bloquer l'UI Qt)."""
    status_ready = pyqtSignal(dict)  # {svc_id: "running"/"stopped"}

    def run(self):
        result = {}
        for svc in SERVICES:
            result[svc["id"]] = "running" if is_port_in_use(svc["port"]) else "stopped"
        self.status_ready.emit(result)


# ============================================================
# Gestion des services (repris de launcher.py)
# ============================================================

processes = {}
is_busy = False


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.15)
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
        for pid in pids:
            kill_process_tree(pid)
    except Exception:
        pass
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


def _emit_log(service, level, message):
    """Émet un log vers l'UI Qt (thread-safe via signal)."""
    if not message or not message.strip():
        return
    msg = message.rstrip()
    if len(msg) > 1000:
        msg = msg[:997] + "..."
    now = time.time()
    dedup_key = (service, _normalize_for_dedup(msg))
    last_time = _recent_msgs.get(dedup_key, 0)
    if now - last_time < _DEDUP_WINDOW:
        return
    _recent_msgs[dedup_key] = now
    if len(_recent_msgs) > 500:
        cutoff = now - _DEDUP_WINDOW * 2
        for k in [k for k, v in _recent_msgs.items() if v < cutoff]:
            del _recent_msgs[k]
    signals.log_received.emit(service, level, msg)


def _pipe_reader(service, pipe, level="info"):
    try:
        for raw in iter(pipe.readline, b""):
            try:
                text = raw.decode("utf-8", errors="replace").rstrip()
            except Exception:
                text = repr(raw)
            if not text:
                continue
            text = _ANSI_RE.sub('', text)
            if not text.strip():
                continue
            lo = text.lower()
            is_err = any(k in lo for k in ("error", "exception", "traceback", "failed", "fatal"))
            if not is_err and _is_noise(text):
                continue
            _emit_log(service, "error" if is_err else level, text)
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


def start_service(name):
    if name == "ollama":
        if is_port_in_use(OLLAMA_PORT):
            _emit_log("launcher", "info", "Ollama déjà actif sur :" + str(OLLAMA_PORT))
            return True
        if not OLLAMA_EXE.exists():
            _emit_log("launcher", "error", "Ollama introuvable : " + str(OLLAMA_EXE))
            return False
        _emit_log("launcher", "info", "Démarrage de Ollama...")
        env = os.environ.copy()
        env["OLLAMA_NUM_PARALLEL"] = "1"
        env["OLLAMA_MAX_LOADED_MODELS"] = "1"
        env["OLLAMA_KEEP_ALIVE"] = "30m"
        env["OLLAMA_KV_CACHE_TYPE"] = "q8_0"
        env["OLLAMA_FLASH_ATTENTION"] = "1"
        proc = subprocess.Popen(
            [str(OLLAMA_EXE), "serve"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes["ollama"] = proc
        _start_readers("ollama", proc)
        ok = wait_for_port(OLLAMA_PORT, timeout=15)
        _emit_log("launcher", "info" if ok else "error",
                  "Ollama " + ("OK :" + str(OLLAMA_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    elif name == "chromadb":
        if is_port_in_use(CHROMADB_PORT):
            _emit_log("launcher", "info", "ChromaDB déjà actif sur :" + str(CHROMADB_PORT))
            return True
        _emit_log("launcher", "info", "Démarrage de ChromaDB...")
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
        _emit_log("launcher", "info" if ok else "error",
                  "ChromaDB " + ("OK :" + str(CHROMADB_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    elif name == "backend":
        if is_port_in_use(BACKEND_PORT):
            _emit_log("launcher", "info", "Backend déjà actif sur :" + str(BACKEND_PORT))
            return True
        _emit_log("launcher", "info", "Démarrage du Backend API...")
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
        _emit_log("launcher", "info" if ok else "error",
                  "Backend " + ("OK :" + str(BACKEND_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    elif name == "frontend":
        if is_port_in_use(FRONTEND_PORT):
            _emit_log("launcher", "info", "Frontend déjà actif sur :" + str(FRONTEND_PORT))
            return True
        _emit_log("launcher", "info", "Démarrage du Frontend...")
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
        _emit_log("launcher", "info" if ok else "error",
                  "Frontend " + ("OK :" + str(FRONTEND_PORT) if ok else "ÉCHEC (timeout)"))
        return ok

    return False


def stop_service(name):
    _emit_log("launcher", "info", "Arrêt de " + name + "...")
    proc = processes.pop(name, None)
    if proc and proc.poll() is None:
        kill_process_tree(proc.pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    if name == "ollama":
        _kill_all_ollama()
        time.sleep(2)
        if is_port_in_use(OLLAMA_PORT):
            _kill_all_ollama()
            time.sleep(1)
    else:
        port_map = {"chromadb": CHROMADB_PORT, "backend": BACKEND_PORT, "frontend": FRONTEND_PORT}
        port = port_map.get(name)
        if port and is_port_in_use(port):
            kill_port(port)
            for _ in range(10):
                if not is_port_in_use(port):
                    break
                time.sleep(0.3)
    port_map_all = {"ollama": OLLAMA_PORT, "chromadb": CHROMADB_PORT,
                    "backend": BACKEND_PORT, "frontend": FRONTEND_PORT}
    port = port_map_all.get(name)
    stopped = not is_port_in_use(port) if port else True
    _emit_log("launcher", "info" if stopped else "error",
              name + (" arrêté" if stopped else " : port encore occupé"))


def start_all():
    global is_busy
    if is_busy:
        return
    is_busy = True
    signals.busy_changed.emit(True)
    _emit_log("launcher", "info", "=== Démarrage de tous les services ===")
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for svc in SERVICES:
            start_service(svc["id"])
        _emit_log("launcher", "info", "=== Démarrage terminé ===")
    finally:
        is_busy = False
        signals.busy_changed.emit(False)
        signals.state_changed.emit({})


def stop_all():
    global is_busy
    if is_busy:
        return
    is_busy = True
    signals.busy_changed.emit(True)
    _emit_log("launcher", "info", "=== Arrêt de tous les services ===")
    try:
        for svc in reversed(SERVICES):
            stop_service(svc["id"])
        _emit_log("launcher", "info", "=== Arrêt terminé ===")
    finally:
        is_busy = False
        signals.busy_changed.emit(False)
        signals.state_changed.emit({})


def reload_all():
    global is_busy
    if is_busy:
        return
    is_busy = True
    signals.busy_changed.emit(True)
    _emit_log("launcher", "info", "=== Rechargement de tous les services ===")
    try:
        for svc in reversed(SERVICES):
            stop_service(svc["id"])
        time.sleep(1)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for svc in SERVICES:
            start_service(svc["id"])
        _emit_log("launcher", "info", "=== Rechargement terminé ===")
    finally:
        is_busy = False
        signals.busy_changed.emit(False)
        signals.state_changed.emit({})


def cleanup():
    for name in ["frontend", "backend", "chromadb"]:
        proc = processes.get(name)
        if proc and proc.poll() is None:
            kill_process_tree(proc.pid)
    for port in [FRONTEND_PORT, BACKEND_PORT, CHROMADB_PORT]:
        if is_port_in_use(port):
            kill_port(port)
    if is_port_in_use(OLLAMA_PORT):
        _kill_all_ollama()
    proc = processes.get("ollama")
    if proc and proc.poll() is None:
        kill_process_tree(proc.pid)


atexit.register(cleanup)


# ============================================================
# Ouverture navigateur (pour "Ouvrir Gustave Code")
# ============================================================

def _find_browser_exe():
    if sys.platform != "win32":
        return None
    for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env_var, "")
        if base:
            exe = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if exe.exists():
                return str(exe)
            exe = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if exe.exists():
                return str(exe)
    return None


_BROWSER_EXE = _find_browser_exe()


def open_gustave():
    url = f"http://localhost:{FRONTEND_PORT}"
    if _BROWSER_EXE:
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
# Interface PyQt6
# ============================================================

STYLESHEET = """
QMainWindow {
    background: transparent;
}
QWidget#wrapper {
    background-color: """ + C_PANEL + """;
    border: 1px solid #2a2318;
    border-radius: 12px;
}
QWidget#central {
    background: transparent;
}

/* Barre de titre custom */
QWidget#title-bar {
    background: """ + C_BG + """;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid #1e1a14;
}
QLabel#tb-title {
    color: """ + C_DIM + """;
}
QPushButton#tb-btn {
    background: transparent;
    border: none;
    color: """ + C_DIM + """;
    font-size: 12px;
    font-weight: normal;
    padding: 0;
    border-radius: 4px;
}
QPushButton#tb-btn:hover {
    background: #2a2318;
    color: """ + C_TEXT + """;
}
QPushButton#tb-close {
    background: transparent;
    border: none;
    color: """ + C_DIM + """;
    font-size: 12px;
    font-weight: normal;
    padding: 0;
    border-radius: 4px;
}
QPushButton#tb-close:hover {
    background: #c03030;
    color: #ffffff;
}

/* Labels */
QLabel {
    color: """ + C_TEXT + """;
    background: transparent;
    border: none;
}
QLabel#logo {
    color: """ + C_GOLD + """;
}
QLabel#title {
    color: """ + C_TEXT + """;
}
QLabel#subtitle {
    color: """ + C_MUTED + """;
}
QLabel#status-bar {
    color: """ + C_DIM + """;
}

/* Services panel */
QWidget#services-panel {
    background: """ + C_BG + """;
    border: 1px solid #1e1a14;
    border-radius: 10px;
}

/* Dot labels */
QLabel#dot-running {
    color: """ + C_GOLD + """;
}
QLabel#dot-stopped {
    color: #4a4035;
}
QLabel#dot-starting {
    color: #dbb960;
}
QLabel#dot-error {
    color: #a03030;
}

/* Buttons */
QPushButton {
    border-radius: 8px;
    font-weight: bold;
    font-size: 13px;
    padding: 10px 16px;
    border: 1px solid """ + C_BORDER + """;
}
QPushButton:disabled {
    color: #4a4035;
    background: #13110e;
    border-color: #1e1a14;
}
QPushButton#start {
    background: #1a2a18;
    color: #7aad6c;
    border-color: #2a3a25;
}
QPushButton#start:hover:!pressed {
    background: #223520;
    border-color: #3a4a30;
}
QPushButton#stop {
    background: #2a1818;
    color: #c08080;
    border-color: #3a2525;
}
QPushButton#stop:hover:!pressed {
    background: #351e1e;
    border-color: #4a3030;
}
QPushButton#reload {
    background: #231f1a;
    color: """ + C_GOLD + """;
    border-color: """ + C_BORDER + """;
}
QPushButton#reload:hover:!pressed {
    background: #2e2820;
}
QPushButton#open-gustave {
    background: """ + C_GOLD + """;
    color: """ + C_BG + """;
    font-size: 15px;
    font-weight: bold;
    padding: 13px;
    border: none;
}
QPushButton#open-gustave:hover:!pressed {
    background: #dbb960;
}
QPushButton#open-gustave:disabled {
    background: #332c24;
    color: #5a5040;
}
QPushButton#quit {
    background: """ + C_DARK + """;
    color: """ + C_MUTED + """;
    font-size: 13px;
    border-color: """ + C_BORDER + """;
}
QPushButton#quit:hover:!pressed {
    background: #2a2318;
    color: """ + C_TEXT + """;
}
QPushButton#update {
    background: """ + C_PANEL + """;
    color: """ + C_MUTED + """;
    font-size: 13px;
    border-color: """ + C_BORDER + """;
}
QPushButton#update:hover:!pressed {
    background: #231f1a;
    color: """ + C_GOLD + """;
}

/* Logs panel */
QWidget#logs-panel {
    background: #080705;
    border: 1px solid #1e1a14;
    border-radius: 10px;
}
QPushButton#logs-toggle {
    background: transparent;
    border: none;
    color: """ + C_MUTED + """;
    font-size: 13px;
    font-weight: bold;
    text-align: left;
    padding: 8px 12px;
}
QPushButton#logs-toggle:hover {
    color: """ + C_TEXT + """;
}
QPushButton#filter-btn {
    background: transparent;
    border: 1px solid transparent;
    color: """ + C_DIM + """;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}
QPushButton#filter-btn:hover {
    color: """ + C_MUTED + """;
}
QPushButton#filter-active {
    background: transparent;
    border: 1px solid """ + C_GOLD + """;
    color: """ + C_GOLD + """;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}
QPushButton#clear-btn {
    background: transparent;
    border: 1px solid """ + C_BORDER + """;
    color: """ + C_DIM + """;
    font-size: 11px;
    padding: 2px 10px;
    border-radius: 4px;
}
QPushButton#clear-btn:hover {
    color: """ + C_MUTED + """;
    border-color: #4a4035;
}
QTextEdit#logs-text {
    background: #080705;
    color: #a09580;
    border: none;
    border-top: 1px solid """ + C_DARK + """;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    selection-background-color: rgba(201, 168, 76, 0.25);
}
QLabel#logs-badge {
    background: #2a2318;
    color: """ + C_MUTED + """;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 7px;
    border-radius: 10px;
}
QLabel#logs-badge-active {
    background: """ + C_GOLD + """;
    color: """ + C_BG + """;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 7px;
    border-radius: 10px;
}

/* Scrollbar */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: #332c24;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #4a4035;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
/* Scrollbar horizontale */
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: #332c24;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #4a4035;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""

# Couleurs des services dans les logs
SVC_COLORS = {
    "ollama": "#c9a84c",
    "chromadb": "#b08050",
    "backend": "#d4a04c",
    "frontend": "#8aad6c",
    "launcher": "#8a7d6b",
}


class GustaveApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gustave Code")
        self.setFixedWidth(WINDOW_WIDTH)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = None

        # Icône (pour la barre des tâches)
        icon_path = PROJECT_ROOT / "gustave-code.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Logs state
        self._logs_open = False
        self._log_count = 0
        self._current_filter = "all"
        self._all_logs = []  # [(svc, lvl, time_str, msg)]
        self._auto_scroll = True

        # Dots et service widgets
        self._dots = {}
        self._svc_states = {svc["id"]: "stopped" for svc in SERVICES}

        self._build_ui()
        self._connect_signals()

        # Polling via QThread (ne bloque PAS l'UI)
        self._poller = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._start_poll)
        self._poll_timer.start(2000)

        # Fast polling timer (500ms pendant les opérations)
        self._fast_poll_timer = QTimer()
        self._fast_poll_timer.timeout.connect(self._start_poll)

        # Hauteur de base = tout sauf le QTextEdit des logs (caché au départ)
        self._current_logs_h = 0
        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())
        self._base_height = self.height()

        # Premier poll
        QTimer.singleShot(100, self._start_poll)

    # ── Drag support (fenêtre frameless) ──

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _build_ui(self):
        # ── Wrapper avec bordure subtile ──
        wrapper = QWidget()
        wrapper.setObjectName("wrapper")
        self.setCentralWidget(wrapper)

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        # ── Barre de titre custom ──
        title_bar = QWidget()
        title_bar.setObjectName("title-bar")
        title_bar.setFixedHeight(36)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(14, 0, 8, 0)
        tb_layout.setSpacing(0)

        tb_title = QLabel("Gustave Code")
        tb_title.setObjectName("tb-title")
        tb_title.setFont(QFont("Segoe UI", 9))
        tb_layout.addWidget(tb_title)
        tb_layout.addStretch()

        btn_minimize = QPushButton("─")
        btn_minimize.setObjectName("tb-btn")
        btn_minimize.setFixedSize(36, 28)
        btn_minimize.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("tb-close")
        btn_close.setFixedSize(36, 28)
        btn_close.clicked.connect(self.close)

        tb_layout.addWidget(btn_minimize)
        tb_layout.addWidget(btn_close)

        wrapper_layout.addWidget(title_bar)

        # ── Contenu principal ──
        central = QWidget()
        central.setObjectName("central")
        wrapper_layout.addWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 16, 32, 20)
        layout.setSpacing(0)

        # ── Logo "G" ──
        logo = QLabel("G")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_font = QFont("Playfair Display")
        if "Playfair Display" not in QFontDatabase.families():
            logo_font = QFont("Georgia")
        logo_font.setPointSize(54)
        logo_font.setWeight(QFont.Weight.Bold)
        logo_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        logo.setFont(logo_font)
        layout.addWidget(logo)

        # ── Ligne dorée ──
        gold_line = QFrame()
        gold_line.setFixedHeight(1)
        gold_line.setFixedWidth(120)
        gold_line.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                                "stop:0 transparent, stop:0.3 rgba(201,168,76,0.25), "
                                "stop:0.5 rgba(201,168,76,0.5), "
                                "stop:0.7 rgba(201,168,76,0.25), stop:1 transparent);")
        line_container = QHBoxLayout()
        line_container.addStretch()
        line_container.addWidget(gold_line)
        line_container.addStretch()
        layout.addLayout(line_container)
        layout.addSpacing(4)

        # ── Titre ──
        title = QLabel("Gustave Code")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Playfair Display" if "Playfair Display" in QFontDatabase.families() else "Georgia")
        title_font.setPointSize(18)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel("Panneau de contrôle")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 10))
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        # ── Services ──
        services_panel = QWidget()
        services_panel.setObjectName("services-panel")
        svc_layout = QVBoxLayout(services_panel)
        svc_layout.setContentsMargins(16, 8, 16, 8)
        svc_layout.setSpacing(0)

        for i, svc in enumerate(SERVICES):
            row = QHBoxLayout()
            row.setContentsMargins(0, 8, 0, 8)

            dot = QLabel("\u25CF")  # ●
            dot.setObjectName("dot-stopped")
            dot.setFont(QFont("Segoe UI", 10))
            dot.setFixedWidth(20)
            self._dots[svc["id"]] = dot

            name_label = QLabel(svc["name"])
            name_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))

            port_label = QLabel(":" + str(svc["port"]))
            port_label.setStyleSheet("color: " + C_DIM + "; font-family: 'Consolas'; font-size: 11px;")
            port_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            row.addWidget(dot)
            row.addWidget(name_label, 1)
            row.addWidget(port_label)
            svc_layout.addLayout(row)

            if i < len(SERVICES) - 1:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background: #1e1a14;")
                svc_layout.addWidget(sep)

        layout.addWidget(services_panel)
        layout.addSpacing(12)

        # ── Boutons principaux ──
        btn_grid = QGridLayout()
        btn_grid.setSpacing(10)

        self._btn_start = QPushButton("\u25B6  Démarrer")
        self._btn_start.setObjectName("start")
        self._btn_start.clicked.connect(self._on_start)

        self._btn_stop = QPushButton("\u25A0  Arrêter")
        self._btn_stop.setObjectName("stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        self._btn_reload = QPushButton("\u21BB  Recharger")
        self._btn_reload.setObjectName("reload")
        self._btn_reload.clicked.connect(self._on_reload)

        btn_grid.addWidget(self._btn_start, 0, 0)
        btn_grid.addWidget(self._btn_stop, 0, 1)
        btn_grid.addWidget(self._btn_reload, 0, 2)
        layout.addLayout(btn_grid)
        layout.addSpacing(10)

        # ── Bouton "Ouvrir Gustave Code" ──
        self._btn_open = QPushButton("Ouvrir Gustave Code")
        self._btn_open.setObjectName("open-gustave")
        self._btn_open.setEnabled(False)
        self._btn_open.clicked.connect(self._on_open)
        layout.addWidget(self._btn_open)
        layout.addSpacing(10)

        # ── Boutons Quitter / Mettre à jour ──
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        btn_quit = QPushButton("Quitter")
        btn_quit.setObjectName("quit")
        btn_quit.clicked.connect(self._on_quit)

        self._btn_update = QPushButton("\u27F3  Mettre à jour")
        self._btn_update.setObjectName("update")
        self._btn_update.clicked.connect(self._on_update)

        bottom_row.addWidget(btn_quit)
        bottom_row.addWidget(self._btn_update)
        layout.addLayout(bottom_row)
        layout.addSpacing(8)

        # ── Status bar ──
        self._status_bar = QLabel("Services arrêtés — Cliquez sur Démarrer")
        self._status_bar.setObjectName("status-bar")
        self._status_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_bar.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self._status_bar)
        layout.addSpacing(12)

        # ── Panneau de logs ──
        self._logs_panel = QWidget()
        self._logs_panel.setObjectName("logs-panel")
        logs_layout = QVBoxLayout(self._logs_panel)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(0)

        # Header des logs
        logs_header = QHBoxLayout()
        logs_header.setContentsMargins(4, 4, 12, 4)
        logs_header.setSpacing(6)

        self._logs_toggle_btn = QPushButton("\u25B6  Logs en direct")
        self._logs_toggle_btn.setObjectName("logs-toggle")
        self._logs_toggle_btn.clicked.connect(self._toggle_logs)

        self._logs_badge = QLabel("0")
        self._logs_badge.setObjectName("logs-badge")
        self._logs_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logs_badge.setMinimumWidth(20)

        logs_header.addWidget(self._logs_toggle_btn)
        logs_header.addWidget(self._logs_badge)
        logs_header.addStretch()

        # Filtres
        self._filter_buttons = {}
        filters = [("all", "TOUS"), ("launcher", "LAUNCHER"), ("ollama", "OLLAMA"),
                   ("chromadb", "CHROMADB"), ("backend", "BACKEND"),
                   ("frontend", "FRONTEND"), ("error", "ERREURS")]
        for fid, flabel in filters:
            btn = QPushButton(flabel)
            btn.setObjectName("filter-active" if fid == "all" else "filter-btn")
            btn.setFixedHeight(20)
            btn.clicked.connect(lambda checked, f=fid: self._set_filter(f))
            logs_header.addWidget(btn)
            self._filter_buttons[fid] = btn

        clear_btn = QPushButton("Effacer")
        clear_btn.setObjectName("clear-btn")
        clear_btn.setFixedHeight(22)
        clear_btn.clicked.connect(self._clear_logs)
        logs_header.addWidget(clear_btn)

        logs_layout.addLayout(logs_header)

        # Zone de texte des logs
        self._logs_text = QTextEdit()
        self._logs_text.setObjectName("logs-text")
        self._logs_text.setReadOnly(True)
        self._logs_text.setVisible(False)
        self._logs_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)  # scroll horizontal
        self._logs_text.verticalScrollBar().rangeChanged.connect(self._on_log_scroll_range_changed)
        logs_layout.addWidget(self._logs_text)

        layout.addWidget(self._logs_panel)

    def _connect_signals(self):
        signals.log_received.connect(self._on_log)
        signals.state_changed.connect(lambda _: self._start_poll())
        signals.busy_changed.connect(self._on_busy_changed)
        signals.quit_ready.connect(self.close)

    # ── Polling (dans un QThread, ne bloque jamais l'UI) ──

    def _start_poll(self):
        if self._poller is not None and self._poller.isRunning():
            return  # Poll déjà en cours
        self._poller = StatusPoller()
        self._poller.status_ready.connect(self._on_status_ready)
        self._poller.start()

    def _on_status_ready(self, statuses):
        """Appelé dans le thread principal Qt avec les résultats du poll."""
        all_running = True
        all_stopped = True
        for svc_id, state in statuses.items():
            old_state = self._svc_states.get(svc_id)
            self._svc_states[svc_id] = state
            if state != old_state:
                self._update_dot(svc_id, state)
            if state != "running":
                all_running = False
            if state != "stopped":
                all_stopped = False

        if not is_busy:
            self._btn_start.setEnabled(not all_running)
            self._btn_stop.setEnabled(not all_stopped)
            self._btn_reload.setEnabled(True)
            self._btn_open.setEnabled(all_running)

        if not is_busy:
            if all_running:
                self._status_bar.setText("Tous les services sont actifs")
                self._status_bar.setStyleSheet("color: " + C_GOLD + ";")
            elif all_stopped:
                self._status_bar.setText("Services arrêtés — Cliquez sur Démarrer")
                self._status_bar.setStyleSheet("color: " + C_DIM + ";")
            else:
                n = sum(1 for s in statuses.values() if s == "running")
                self._status_bar.setText(f"{n}/4 services actifs")
                self._status_bar.setStyleSheet("color: " + C_DIM + ";")

    def _update_dot(self, svc_id, state):
        dot = self._dots.get(svc_id)
        if dot:
            dot.setObjectName("dot-" + state)
            dot.style().unpolish(dot)
            dot.style().polish(dot)

    # ── Actions ──

    def _on_busy_changed(self, busy):
        if busy:
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(False)
            self._btn_reload.setEnabled(False)
            self._btn_open.setEnabled(False)
            self._status_bar.setText("Opération en cours...")
            self._status_bar.setStyleSheet("color: #dbb960;")
            # Accélérer le polling
            self._fast_poll_timer.start(500)
        else:
            self._fast_poll_timer.stop()

    def _on_start(self):
        self._on_busy_changed(True)
        # Dots en "starting"
        for svc_id, dot in self._dots.items():
            if self._svc_states.get(svc_id) != "running":
                self._update_dot(svc_id, "starting")
        threading.Thread(target=start_all, daemon=True).start()

    def _on_stop(self):
        self._on_busy_changed(True)
        for svc_id, dot in self._dots.items():
            if self._svc_states.get(svc_id) == "running":
                self._update_dot(svc_id, "starting")
        threading.Thread(target=stop_all, daemon=True).start()

    def _on_reload(self):
        self._on_busy_changed(True)
        for svc_id in self._dots:
            self._update_dot(svc_id, "starting")
        threading.Thread(target=reload_all, daemon=True).start()

    def _on_open(self):
        open_gustave()

    def _on_quit(self):
        reply = QMessageBox.question(
            self, "Quitter",
            "Arrêter tous les services et quitter Gustave Code ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._shutting_down = True
            self._status_bar.setText("Arrêt en cours...")
            self._status_bar.setStyleSheet("color: #dbb960;")
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(False)
            self._btn_reload.setEnabled(False)
            self._btn_open.setEnabled(False)
            threading.Thread(target=self._do_quit, daemon=True).start()

    def _do_quit(self):
        stop_all()
        signals.quit_ready.emit()  # → self.close() sur le thread principal

    def _on_update(self):
        """Relance l'app (les services restent actifs)."""
        python = sys.executable
        os.execv(python, [python, str(Path(__file__).resolve())])

    # ── Logs ──

    def _on_log(self, service, level, message):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self._all_logs.append((service, level, t, message))
        if len(self._all_logs) > MAX_LOG_LINES:
            self._all_logs = self._all_logs[-MAX_LOG_LINES:]

        self._log_count += 1
        badge_text = str(self._log_count)
        self._logs_badge.setText(badge_text)
        if self._log_count > 0:
            self._logs_badge.setObjectName("logs-badge-active")
        else:
            self._logs_badge.setObjectName("logs-badge")
        self._logs_badge.style().unpolish(self._logs_badge)
        self._logs_badge.style().polish(self._logs_badge)

        # Appliquer le filtre
        if not self._matches_filter(service, level):
            return

        self._append_log_line(service, level, t, message)

    def _matches_filter(self, svc, lvl):
        if self._current_filter == "all":
            return True
        if self._current_filter == "error":
            return lvl == "error"
        return svc == self._current_filter

    def _calc_logs_height(self):
        """Hauteur idéale basée sur le contenu réel du document."""
        doc_h = int(self._logs_text.document().size().height()) + 8
        return max(LOGS_MIN_HEIGHT, min(doc_h, LOGS_MAX_HEIGHT))

    def _update_logs_height(self):
        """Adapte la hauteur du QTextEdit au contenu visible (delta direct)."""
        if not self._logs_open or getattr(self, '_refreshing', False):
            return
        new_h = self._calc_logs_height()
        if new_h != self._current_logs_h:
            self._logs_text.setFixedHeight(new_h)
            self._current_logs_h = new_h
            self.setFixedHeight(self._base_height + new_h)

    def _append_log_line(self, service, level, t, message):
        svc_color = SVC_COLORS.get(service, C_MUTED)
        msg_color = "#c08080" if level == "error" else ("#d4b870" if level == "warn" else "#a09580")
        if service == "launcher":
            msg_color = C_MUTED

        html = (f'<span style="color:#3d3428;">{t}</span>&nbsp;&nbsp;'
                f'<span style="color:{svc_color};font-weight:600;">{service:8s}</span>&nbsp;&nbsp;'
                f'<span style="color:{msg_color};">{self._escape_html(message)}</span>')

        self._logs_text.append(html)
        self._update_logs_height()

    @staticmethod
    def _escape_html(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _on_log_scroll_range_changed(self, min_val, max_val):
        if self._auto_scroll:
            self._logs_text.verticalScrollBar().setValue(max_val)

    def _toggle_logs(self):
        self._logs_open = not self._logs_open
        self._logs_text.setVisible(self._logs_open)

        if self._logs_open:
            self._logs_toggle_btn.setText("\u25BC  Logs en direct")
            h = self._calc_logs_height()
            self._current_logs_h = h
            self._logs_text.setFixedHeight(h)
            self.setFixedHeight(self._base_height + h)
            sb = self._logs_text.verticalScrollBar()
            sb.setValue(sb.maximum())
        else:
            self._logs_toggle_btn.setText("\u25B6  Logs en direct")
            self._current_logs_h = 0
            self.setFixedHeight(self._base_height)

    def _set_filter(self, filter_id):
        self._current_filter = filter_id
        for fid, btn in self._filter_buttons.items():
            btn.setObjectName("filter-active" if fid == filter_id else "filter-btn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._refresh_logs_display()

    def _refresh_logs_display(self):
        self._refreshing = True
        self._logs_text.clear()
        for svc, lvl, t, msg in self._all_logs:
            if self._matches_filter(svc, lvl):
                self._append_log_line(svc, lvl, t, msg)
        self._refreshing = False
        self._update_logs_height()

    def _clear_logs(self):
        self._all_logs.clear()
        self._log_count = 0
        self._logs_text.clear()
        self._logs_badge.setText("0")
        self._logs_badge.setObjectName("logs-badge")
        self._logs_badge.style().unpolish(self._logs_badge)
        self._logs_badge.style().polish(self._logs_badge)
        self._update_logs_height()

    # ── Fermeture ──

    def closeEvent(self, event):
        if hasattr(self, '_shutting_down') and self._shutting_down:
            event.accept()
            return
        reply = QMessageBox.question(
            self, "Quitter",
            "Arrêter tous les services et quitter Gustave Code ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._status_bar.setText("Arrêt en cours...")
            stop_all()
            event.accept()
        else:
            event.ignore()


# ============================================================
# Point d'entrée
# ============================================================

def main():
    # Redirection stdout/stderr pour pythonw
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    # Charger Playfair Display (embarquée dans fonts/)
    font_path = PROJECT_ROOT / "fonts" / "PlayfairDisplay.ttf"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))

    window = GustaveApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
