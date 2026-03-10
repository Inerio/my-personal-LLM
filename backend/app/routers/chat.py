"""
Route Chat — Gustave Code
Endpoint principal avec streaming SSE (Server-Sent Events).

Keepalive : un commentaire SSE (": keepalive") est envoyé toutes les 15 s
quand l'agent ne produit pas d'événement (ex. chargement modèle 70B, longue
inférence avec CPU offloading). Cela maintient la connexion active à travers
les proxies (React dev server, Nginx, etc.).
"""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest
from app.config import ModelProfile
from app.services.agent import agent_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Intervalle keepalive SSE (secondes)
_KEEPALIVE_INTERVAL = 15.0


def _format_error(err_msg: str) -> str:
    """Traduire les erreurs techniques en messages lisibles."""
    low = err_msg.lower()
    if "connection refused" in low or "connecterror" in low:
        return "Impossible de contacter Ollama. Vérifiez qu'il est démarré via le launcher."
    if "404" in err_msg and "model" in low:
        return "Modèle introuvable. Vérifiez qu'il est installé (ollama list)."
    if "timeout" in low or "timed out" in low:
        return "Délai d'attente dépassé. Le modèle met trop de temps à répondre."
    if "out of memory" in low or "oom" in low:
        return "Mémoire insuffisante. Essayez un modèle plus léger (profil Rapide)."
    return err_msg


@router.post("")
async def chat(request: ChatRequest):
    """
    Envoyer un message et recevoir une réponse en streaming SSE.

    Le stream envoie les événements suivants :
    - `conversation_id` : ID de la conversation (envoyé en premier)
    - `token` : Chaque token de la réponse au fur et à mesure
    - `thinking` : Tokens de réflexion (bloc <think>)
    - `tool_start` : Début d'utilisation d'un outil
    - `tool_end` : Fin d'utilisation d'un outil avec résultat
    - `done` : Fin de la réponse avec métadonnées
    - `error` : En cas d'erreur
    """
    profile = ModelProfile(request.profile.value)

    logger.info(
        f"Chat | Profil: {profile.value} | "
        f"Conv: {request.conversation_id or 'nouvelle'} | "
        f"Message: {request.message[:80]}..."
    )

    async def event_generator():
        """Générateur SSE avec keepalive pendant les longues inférences."""
        _SENTINEL = object()
        queue: asyncio.Queue = asyncio.Queue()

        async def _produce():
            """Produit les événements de l'agent dans une queue."""
            try:
                async for ev in agent_service.chat_stream(
                    message=request.message,
                    conversation_id=request.conversation_id,
                    profile=profile,
                ):
                    await queue.put(ev)
            except Exception as exc:
                logger.error(f"Erreur agent stream: {exc}", exc_info=True)
                await queue.put({
                    "event": "error",
                    "data": {"message": _format_error(str(exc))},
                })
            finally:
                await queue.put(_SENTINEL)

        task = asyncio.create_task(_produce())

        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_KEEPALIVE_INTERVAL
                    )
                except asyncio.TimeoutError:
                    # Commentaire SSE — maintient la connexion active,
                    # ignoré par les parsers SSE côté client
                    yield ": keepalive\n\n"
                    continue

                if event is _SENTINEL:
                    break

                event_type = event.get("event", "unknown")
                event_data = event.get("data", {})
                yield (
                    f"event: {event_type}\n"
                    f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                )

        except GeneratorExit:
            logger.info("Client a fermé la connexion SSE")
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
