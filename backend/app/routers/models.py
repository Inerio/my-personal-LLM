"""
Routes Modèles — Gustave Code
Liste des modèles Ollama et profils de qualité disponibles.
"""

from fastapi import APIRouter

from app.models.schemas import ProfileResponse, ModelResponse
from app.services.llm_service import llm_service

router = APIRouter()


@router.get("/profiles", response_model=list[ProfileResponse])
async def get_profiles():
    """
    Lister les 3 profils de qualité disponibles.
    Chaque profil correspond à un modèle différent avec ses caractéristiques.
    """
    profiles = llm_service.get_all_profiles()

    return [
        ProfileResponse(
            id=profile_data["id"],
            name=profile_data["name"],
            description=profile_data["description"],
            base_model=profile_data["base_model"],
            parameters=profile_data["parameters"],
            quantization=profile_data["quantization"],
            estimated_ram=profile_data["estimated_ram"],
            speed=profile_data["speed"],
        )
        for profile_data in profiles.values()
    ]


@router.get("", response_model=list[ModelResponse])
async def get_ollama_models():
    """
    Lister tous les modèles disponibles dans Ollama.
    """
    models = await llm_service.list_ollama_models()

    return [
        ModelResponse(
            name=model.get("name", "unknown"),
            size=_format_size(model.get("size", 0)),
            modified_at=model.get("modified_at", ""),
        )
        for model in models
    ]


def _format_size(size_bytes: int) -> str:
    """Formater la taille en bytes vers une unité lisible."""
    if size_bytes == 0:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
