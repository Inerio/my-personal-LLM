"""
Route Health Check — Gustave Code
Vérification de l'état de tous les services.
"""

from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.config import settings, PROFILE_MODEL_MAP

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Vérifier l'état de tous les services :
    - Ollama (LLM local)
    - SQLite (base de données)
    - ChromaDB (mémoire vectorielle)
    """
    result = HealthResponse(status="ok")

    # Vérifier Ollama
    try:
        result.ollama_connected = await llm_service.check_ollama_connection()
    except Exception:
        result.ollama_connected = False

    # Vérifier SQLite
    try:
        from app.database.db import engine, sa_text
        with engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        result.database_connected = True
    except Exception:
        result.database_connected = False

    # Vérifier ChromaDB
    result.chromadb_connected = memory_service.is_available

    # Modèle actif
    profile = settings.default_model_profile
    result.active_model = PROFILE_MODEL_MAP.get(profile, "unknown")

    # Status global
    if not result.ollama_connected and settings.llm_provider == "ollama":
        result.status = "degraded"
    if not result.database_connected:
        result.status = "error"

    return result
