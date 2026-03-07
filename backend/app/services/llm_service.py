"""
Service LLM — Gustave Code
Abstraction multi-fournisseur avec profils de qualité.
Supporte : Ollama (local), OpenAI, Anthropic.
"""

import logging
from typing import Optional

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from app.config import (
    settings,
    ModelProfile,
    PROFILE_MODEL_MAP,
    PROFILE_INFO,
    QUALITY_INFERENCE_PARAMS,
)

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service centralisé pour la gestion des LLMs.

    Supporte 3 profils de qualité (ultra, quality, fast) avec Ollama,
    et des fallbacks vers OpenAI/Anthropic si configurés.
    """

    def __init__(self):
        self.provider = settings.llm_provider
        self.ollama_base_url = settings.ollama_base_url
        self.default_profile = settings.default_model_profile

    def get_llm(
        self,
        profile: Optional[ModelProfile] = None,
        streaming: bool = True,
    ) -> BaseChatModel:
        """
        Obtenir une instance LLM selon le profil de qualité.

        Args:
            profile: Profil de qualité (ultra, quality, fast). None = défaut.
            streaming: Activer le streaming token par token.

        Returns:
            Instance BaseChatModel configurée.
        """
        if profile is None:
            profile = self.default_profile

        if self.provider == "ollama":
            return self._get_ollama_llm(profile, streaming)
        elif self.provider == "openai":
            return self._get_openai_llm(streaming)
        elif self.provider == "anthropic":
            return self._get_anthropic_llm(streaming)
        else:
            raise ValueError(f"Fournisseur LLM inconnu: {self.provider}")

    def _get_ollama_llm(
        self,
        profile: ModelProfile,
        streaming: bool,
    ) -> ChatOllama:
        """Créer une instance Ollama avec les paramètres qualité optimisés."""
        model_name = PROFILE_MODEL_MAP[profile]
        params = QUALITY_INFERENCE_PARAMS.copy()

        logger.info(f"Chargement modele Ollama: {model_name} (profil: {profile.value})")

        return ChatOllama(
            model=model_name,
            base_url=self.ollama_base_url,
            streaming=streaming,
            temperature=params["temperature"],
            top_p=params["top_p"],
            top_k=params["top_k"],
            repeat_penalty=params["repeat_penalty"],
            num_ctx=params["num_ctx"],
            num_predict=params["num_predict"],
            # Note: num_gpu et num_thread sont définis dans le Modelfile
        )

    def _get_openai_llm(self, streaming: bool) -> ChatOpenAI:
        """Créer une instance OpenAI (fallback cloud)."""
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY non configurée")

        logger.info(f"Utilisation OpenAI: {settings.openai_model}")

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            streaming=streaming,
            temperature=0.7,
            max_tokens=None,  # Pas de limite
        )

    def _get_anthropic_llm(self, streaming: bool) -> ChatAnthropic:
        """Créer une instance Anthropic (fallback cloud)."""
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY non configurée")

        logger.info(f"Utilisation Anthropic: {settings.anthropic_model}")

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            streaming=streaming,
            temperature=0.7,
            max_tokens=8192,
        )

    async def check_ollama_connection(self) -> bool:
        """Vérifier que Ollama est accessible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama non accessible: {e}")
            return False

    async def list_ollama_models(self) -> list[dict]:
        """Lister les modèles disponibles dans Ollama."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
                return []
        except Exception as e:
            logger.error(f"Erreur liste modèles Ollama: {e}")
            return []

    def get_profile_info(self, profile: Optional[ModelProfile] = None) -> dict:
        """Obtenir les informations descriptives d'un profil."""
        if profile is None:
            profile = self.default_profile
        return PROFILE_INFO.get(profile, {})

    def get_all_profiles(self) -> dict:
        """Obtenir les informations de tous les profils."""
        return {
            profile.value: {
                "id": profile.value,
                **info,
            }
            for profile, info in PROFILE_INFO.items()
        }


# Instance globale (singleton)
llm_service = LLMService()
