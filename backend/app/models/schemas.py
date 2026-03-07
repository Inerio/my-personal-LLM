"""
Schémas Pydantic — Gustave Code
Modèles de données pour l'API.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


# ============================================
# Enums
# ============================================

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ModelProfileEnum(str, Enum):
    LLAMA = "llama"
    MIXTRAL = "mixtral"
    FAST = "fast"


# ============================================
# Requêtes
# ============================================

class ChatRequest(BaseModel):
    """Requête pour envoyer un message au chat."""
    message: str = Field(..., min_length=1, description="Message de l'utilisateur")
    conversation_id: Optional[str] = Field(
        default=None,
        description="ID de la conversation existante (None = nouvelle conversation)"
    )
    profile: ModelProfileEnum = Field(
        default=ModelProfileEnum.FAST,
        description="Profil de qualité du modèle"
    )


# ============================================
# Réponses
# ============================================

class MessageResponse(BaseModel):
    """Un message dans une conversation."""
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    thinking_content: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    extra_metadata: Optional[dict] = None
    tokens_used: Optional[int] = None
    thinking_time_ms: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    """Une conversation avec ses métadonnées."""
    id: str
    title: str
    model_profile: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    message_count: Optional[int] = None

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    """Détails complets d'une conversation avec messages."""
    id: str
    title: str
    model_profile: Optional[str] = None
    created_at: datetime
    messages: List[MessageResponse] = []

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    """Information sur un profil de qualité."""
    id: str
    name: str
    description: str
    base_model: str
    parameters: str
    quantization: str
    estimated_ram: str
    speed: str


class ModelResponse(BaseModel):
    """Information sur un modèle Ollama disponible."""
    name: str
    size: Optional[str] = None
    modified_at: Optional[str] = None


class HealthResponse(BaseModel):
    """Reponse du health check."""
    status: str = "ok"
    ollama_connected: bool = False
    database_connected: bool = False
    chromadb_connected: bool = False
    active_model: Optional[str] = None
