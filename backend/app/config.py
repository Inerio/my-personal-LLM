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
        "description": "Qwen 2.5 14B Abliterated — Réponses rapides, non censuré",
        "base_model": "huihui_ai/qwen2.5-abliterate:14b-instruct-q8_0",
        "parameters": "14B",
        "quantization": "Q8_0",
        "estimated_ram": "~15 GB",
        "speed": "Rapide",
    },
}

# Paramètres d'inférence optimisés pour la qualité
QUALITY_INFERENCE_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_ctx": 32768,       # Fenêtre de contexte large
    "num_predict": -1,       # Pas de limite de longueur
    "num_gpu": 99,           # Maximum de couches en VRAM
    "num_thread": 16,        # 16 cœurs physiques du 5950X
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
