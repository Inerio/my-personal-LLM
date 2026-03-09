"""
Configuration de l'application — Gustave Code
Gestion des profils de qualité et paramètres globaux.
"""

from enum import Enum
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional

# Résoudre le chemin du .env (racine du projet, un niveau au-dessus de backend/)
_THIS_DIR = Path(__file__).resolve().parent.parent  # backend/
_PROJECT_ROOT = _THIS_DIR.parent  # racine du projet
_ENV_FILE = _PROJECT_ROOT / ".env" if (_PROJECT_ROOT / ".env").exists() else _THIS_DIR / ".env"


class ModelProfile(str, Enum):
    """Profils de qualité disponibles."""
    LLAMA = "llama"
    MIXTRAL = "mixtral"
    FAST = "fast"


# Mapping profil → nom du modèle Ollama personnalisé
PROFILE_MODEL_MAP = {
    ModelProfile.LLAMA: "gustave-llama",
    ModelProfile.MIXTRAL: "gustave-mixtral",
    ModelProfile.FAST: "gustave-fast",
}

# Informations descriptives des profils
PROFILE_INFO = {
    ModelProfile.LLAMA: {
        "name": "LLaMA 3.3",
        "description": "LLaMA 3.3 70B Abliterated — Meta, multilingue 128K contexte, non censuré",
        "base_model": "huihui_ai/llama3.3-abliterated:70b-instruct-q4_K_M",
        "parameters": "70B",
        "quantization": "Q4_K_M",
        "estimated_ram": "~43 GB",
        "speed": "Lent (CPU offloading)",
    },
    ModelProfile.MIXTRAL: {
        "name": "Dolphin Mixtral 8x22B",
        "description": "Dolphin Mixtral 8x22B — Eric Hartford, MoE non censuré",
        "base_model": "dolphin-mixtral:8x22b",
        "parameters": "8x22B (141B)",
        "quantization": "Q4_0",
        "estimated_ram": "~80 GB",
        "speed": "Très lent (RAM intensive)",
    },
    ModelProfile.FAST: {
        "name": "Rapide",
        "description": "JOSIEFIED Qwen3 8B — Ablitéré + fine-tuné, ultra-rapide, non censuré",
        "base_model": "goekdenizguelmez/JOSIEFIED-Qwen3:8b-q8_0",
        "parameters": "8B",
        "quantization": "Q8_0",
        "estimated_ram": "~9 GB (100% VRAM)",
        "speed": "Très rapide",
    },
}

# Paramètres d'inférence par profil — adaptés à la VRAM/RAM disponible
# RTX 3080 12 GB VRAM + 64 GB RAM + Ryzen 9 5950X (16 cores / 32 threads)
PROFILE_INFERENCE_PARAMS = {
    ModelProfile.FAST: {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "num_ctx": 16384,       # 8B Q8_0 ≈8.7 GB + KV cache 16K ≈1 GB → 100% en VRAM (RTX 3080 12 GB)
        "num_predict": 8192,     # Limite raisonnable — évite les générations infinies
        "num_thread": 0,         # 0 = auto-detect (GPU-only, threads CPU non utilisés)
    },
    ModelProfile.LLAMA: {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "num_ctx": 8192,        # 70B = CPU offloading, KV cache réduit (~2.5 GiB vs ~5 GiB)
        "num_predict": 4096,    # Limite raisonnable pour éviter les inférences infinies
        "num_thread": 16,        # Cores physiques uniquement (5950X) — évite le cache thrashing
    },
    ModelProfile.MIXTRAL: {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "num_ctx": 4096,        # 8x22B (~80 GB) — contexte minimal (KV cache ÷2 vs 8K)
        "num_predict": 2048,    # Limite courte — chaque token coûte cher en RAM
        "num_thread": 16,        # Cores physiques uniquement (5950X)
    },
}

# Limites de contexte par profil — contrôle la quantité de données envoyées au LLM
# Crucial pour les profils lourds : chaque token compte quand le contexte est à 8K
PROFILE_CONTEXT_LIMITS = {
    ModelProfile.FAST: {
        "max_history": 20,       # Messages d'historique (16K contexte)
        "max_msg_chars": 3000,   # Chars max par message dans l'historique (~750 tokens)
        "max_memory_results": 3, # Résultats mémoire long-terme injectés
        "max_memory_doc_chars": 600,  # Chars max par document mémoire
        "enable_long_term_memory": True,
    },
    ModelProfile.LLAMA: {
        "max_history": 10,       # Historique réduit (8K contexte, CPU lent)
        "max_msg_chars": 1500,   # ~375 tokens max par message
        "max_memory_results": 2, # Juste les 2 souvenirs les plus pertinents
        "max_memory_doc_chars": 400,  # Excerpts courts
        "enable_long_term_memory": True,
    },
    ModelProfile.MIXTRAL: {
        "max_history": 4,        # Historique ultra-minimal (4K contexte, modèle massif)
        "max_msg_chars": 600,    # ~150 tokens max par message
        "max_memory_results": 0, # Pas de mémoire long-terme (chaque token est précieux)
        "max_memory_doc_chars": 0,
        "enable_long_term_memory": False,  # Désactivé pour Mixtral
    },
}

# Timeout HTTP Ollama par profil (secondes)
# Temps max pour recevoir un chunk (inclut le chargement initial du modèle)
PROFILE_TIMEOUTS = {
    ModelProfile.FAST: 120,      # 2 min  — modèle rapide en VRAM
    ModelProfile.LLAMA: 600,     # 10 min — CPU offloading, chargement lent
    ModelProfile.MIXTRAL: 900,   # 15 min — très lent, modèle massif
}

# Durée de rétention du modèle en mémoire après la dernière requête
# Switch de profil = déchargement immédiat (grâce à OLLAMA_MAX_LOADED_MODELS=1)
# Ce timer ne concerne que l'inactivité SANS switch de profil
PROFILE_KEEP_ALIVE = {
    ModelProfile.FAST: "15m",    # 8B 100% VRAM — très léger, garde en mémoire
    ModelProfile.LLAMA: "3m",    # 70B (~43 GB RAM) — libère vite si inactif
    ModelProfile.MIXTRAL: "0",   # 8x22B (~80 GB RAM) — décharge IMMÉDIATEMENT après réponse
}


class Settings(BaseSettings):
    """Configuration globale de l'application."""

    # --- Fournisseur LLM ---
    llm_provider: str = Field(default="ollama", description="ollama, openai, ou anthropic")

    # --- Ollama ---
    ollama_base_url: str = Field(default="http://localhost:11434")
    default_model_profile: ModelProfile = Field(default=ModelProfile.FAST)

    # --- OpenAI (fallback) ---
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4o")

    # --- Anthropic (fallback) ---
    anthropic_api_key: Optional[str] = Field(default=None)
    anthropic_model: str = Field(default="claude-sonnet-4-20250514")

    # --- Outils ---
    tavily_api_key: Optional[str] = Field(default=None)
    openweathermap_api_key: Optional[str] = Field(default=None)

    # --- Base de données ---
    database_url: str = Field(default="sqlite:///./data/conversations.db")
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8001)

    # --- Serveur ---
    backend_port: int = Field(default=8000)
    frontend_port: int = Field(default=3000)
    cors_origins: str = Field(default="http://localhost:3000")

    # --- Mémoire ---
    max_conversation_history: int = Field(
        default=50,
        description="Nombre max de messages à inclure dans le contexte"
    )
    enable_long_term_memory: bool = Field(
        default=True,
        description="Activer la mémoire long-terme via ChromaDB"
    )
    memory_search_results: int = Field(
        default=5,
        description="Nombre de résultats de mémoire à inclure"
    )

    @field_validator(
        "tavily_api_key",
        "openweathermap_api_key",
        "openai_api_key",
        "anthropic_api_key",
        mode="before",
    )
    @classmethod
    def _strip_placeholder_keys(cls, v):
        """Convertir les clés API placeholder (.env template) en None."""
        if not v or not isinstance(v, str):
            return None
        # Détecter les valeurs placeholder courantes
        low = v.strip().lower()
        if "your-key" in low or "your_key" in low or low in ("", "none", "null"):
            return None
        return v.strip()

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Instance globale
settings = Settings()
