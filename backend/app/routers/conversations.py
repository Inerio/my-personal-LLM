"""
Routes Conversations — Gustave Code
CRUD pour la gestion des conversations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.schemas import (
    ConversationResponse,
    ConversationDetailResponse,
    MessageResponse,
)
from pydantic import BaseModel

from app.database.db import (
    get_db,
    list_conversations,
    get_conversation,
    delete_conversation,
    delete_all_conversations,
    get_conversation_messages,
    update_conversation_title,
    add_message,
)
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# Routes NON paramétriques (avant /{conversation_id})
# ============================================

@router.delete("/memory/purge")
async def purge_memory():
    """
    Purger toute la mémoire long-terme (ChromaDB).
    Supprime l'intégralité des souvenirs de conversations passées.
    """
    result = memory_service.purge_all_memories()
    logger.info(f"Purge mémoire long-terme : {result}")
    return result


@router.delete("/all")
async def remove_all_conversations(db: Session = Depends(get_db)):
    """
    Supprimer toutes les conversations + purger la mémoire long-terme.
    Opération nucléaire : remet tout à zéro.
    """
    # 1. Supprimer toutes les conversations SQLite
    count = delete_all_conversations(db)

    # 2. Purger toute la mémoire ChromaDB
    purge_result = memory_service.purge_all_memories()

    logger.info(
        f"Suppression totale : {count} conversations supprimées, "
        f"mémoire purgée : {purge_result}"
    )
    return {
        "status": "purged",
        "conversations_deleted": count,
        "memory": purge_result,
    }


# ============================================
# Routes CRUD conversations
# ============================================

@router.get("", response_model=list[ConversationResponse])
async def get_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Lister toutes les conversations (les plus récentes d'abord)."""
    conversations = list_conversations(db, limit=limit, offset=offset)

    return [
        ConversationResponse(
            id=conv.id,
            title=conv.title,
            model_profile=conv.model_profile,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=conv.message_count,
        )
        for conv in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Récupérer une conversation avec tous ses messages."""
    conv = get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")

    messages = get_conversation_messages(db, conversation_id)

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        model_profile=conv.model_profile,
        created_at=conv.created_at,
        messages=[
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                thinking_content=msg.thinking_content,
                tool_calls=msg.tool_calls,
                extra_metadata=msg.extra_metadata,
                tokens_used=msg.tokens_used,
                thinking_time_ms=msg.thinking_time_ms,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
    )


@router.delete("/{conversation_id}")
async def remove_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Supprimer une conversation et tous ses messages + mémoire ChromaDB."""
    success = delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")

    # Nettoyer aussi la mémoire long-terme (ChromaDB)
    memory_service.delete_conversation_memories(conversation_id)

    logger.info(f"Conversation supprimée (DB + ChromaDB): {conversation_id}")
    return {"status": "deleted", "conversation_id": conversation_id}


@router.patch("/{conversation_id}/title")
async def rename_conversation(
    conversation_id: str,
    title: str = Query(..., min_length=1, max_length=200),
    db: Session = Depends(get_db),
):
    """Renommer une conversation."""
    success = update_conversation_title(db, conversation_id, title)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")

    return {"status": "updated", "conversation_id": conversation_id, "title": title}


class SavePartialRequest(BaseModel):
    content: str
    thinking_content: Optional[str] = None


@router.post("/{conversation_id}/save-partial")
async def save_partial_response(
    conversation_id: str,
    body: SavePartialRequest,
    db: Session = Depends(get_db),
):
    """Sauvegarder une réponse partielle quand l'utilisateur annule le stream."""
    conv = get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")

    if not body.content.strip():
        return {"status": "skipped", "reason": "empty content"}

    msg = add_message(
        db,
        conversation_id,
        "assistant",
        body.content,
        thinking_content=body.thinking_content,
    )
    logger.info(f"Réponse partielle sauvegardée: {conversation_id} ({len(body.content)} chars)")
    return {"status": "saved", "message_id": msg.id}
