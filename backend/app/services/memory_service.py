"""
Service de Mémoire — Gustave Code
Gestion de la mémoire court-terme (SQLite) et long-terme (ChromaDB).
"""

import logging
from typing import Optional

import chromadb
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.config import settings
from app.database.db import get_db_session, get_conversation_messages

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Service de mémoire à deux niveaux :
    - Court terme : Messages récents de la conversation (SQLite)
    - Long terme : Recherche sémantique sur l'historique (ChromaDB)
    """

    def __init__(self):
        self.chroma_client: Optional[chromadb.HttpClient] = None
        self.collection = None
        self._initialized = False

    def initialize(self):
        """Initialiser la connexion ChromaDB."""
        try:
            self.chroma_client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
            # Créer ou récupérer la collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="conversation_memory",
                metadata={"hnsw:space": "cosine"},
            )
            self._initialized = True
            logger.info(f"ChromaDB initialise — {self.collection.count()} documents en memoire")
        except Exception as e:
            logger.warning(f"ChromaDB non disponible: {e}")
            self._initialized = False

    @property
    def is_available(self) -> bool:
        return self._initialized and self.collection is not None

    # ============================================
    # Mémoire court-terme (SQLite)
    # ============================================

    def get_conversation_history(
        self,
        conversation_id: str,
        max_messages: Optional[int] = None,
    ) -> list:
        """
        Récupérer l'historique récent d'une conversation depuis SQLite.
        Retourne des objets LangChain Message pour injection dans le prompt.
        """
        if max_messages is None:
            max_messages = settings.max_conversation_history

        with get_db_session() as db:
            messages = get_conversation_messages(db, conversation_id)

            # Prendre les N derniers messages
            recent = messages[-max_messages:] if len(messages) > max_messages else messages

            # Convertir en messages LangChain
            langchain_messages = []
            for msg in recent:
                if msg.role == "user":
                    langchain_messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    langchain_messages.append(AIMessage(content=msg.content))
                elif msg.role == "system":
                    langchain_messages.append(SystemMessage(content=msg.content))
                # Les messages "tool" sont gérés par l'agent

            return langchain_messages

    # ============================================
    # Mémoire long-terme (ChromaDB)
    # ============================================

    def store_interaction(
        self,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
        metadata: Optional[dict] = None,
    ):
        """
        Stocker une interaction (question + réponse) dans la mémoire long-terme.
        """
        if not self.is_available or not settings.enable_long_term_memory:
            return

        try:
            import uuid

            # Créer un document combiné (question + réponse)
            document = f"Question: {user_message}\nRéponse: {assistant_response}"

            doc_metadata = {
                "conversation_id": conversation_id,
                "type": "interaction",
            }
            if metadata:
                doc_metadata.update(metadata)

            self.collection.add(
                documents=[document],
                metadatas=[doc_metadata],
                ids=[str(uuid.uuid4())],
            )
            logger.debug("Interaction stockee en memoire long-terme")

        except Exception as e:
            logger.error(f"Erreur stockage mémoire long-terme: {e}")

    def search_relevant_context(
        self,
        query: str,
        n_results: Optional[int] = None,
        exclude_conversation_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Rechercher des interactions passées pertinentes pour enrichir le contexte.

        Args:
            query: La question de l'utilisateur
            n_results: Nombre de résultats (défaut: settings)
            exclude_conversation_id: Exclure la conversation actuelle

        Returns:
            Liste de dicts {document, metadata, distance}
        """
        if not self.is_available or not settings.enable_long_term_memory:
            return []

        if n_results is None:
            n_results = settings.memory_search_results

        try:
            # Préparer le filtre
            where_filter = None
            if exclude_conversation_id:
                where_filter = {
                    "conversation_id": {"$ne": exclude_conversation_id}
                }

            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )

            # Formater les résultats
            context_items = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else None
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}

                    # Ne garder que les résultats pertinents (distance < 0.7)
                    if distance is not None and distance > 0.7:
                        continue

                    context_items.append({
                        "document": doc,
                        "metadata": metadata,
                        "relevance": round(1 - (distance or 0), 3),
                    })

            return context_items

        except Exception as e:
            logger.error(f"Erreur recherche mémoire long-terme: {e}")
            return []

    def format_context_for_prompt(self, context_items: list[dict]) -> str:
        """
        Formater le contexte de mémoire long-terme pour injection dans le prompt.
        """
        if not context_items:
            return ""

        parts = ["[Contexte de conversations précédentes pertinentes:]"]
        for i, item in enumerate(context_items, 1):
            relevance = item.get("relevance", 0)
            parts.append(f"\n--- Mémoire {i} (pertinence: {relevance:.0%}) ---")
            parts.append(item["document"])

        return "\n".join(parts)

    def delete_conversation_memories(self, conversation_id: str):
        """Supprimer toutes les entrées ChromaDB liées à une conversation."""
        if not self.is_available:
            return
        try:
            # Chercher les IDs des documents de cette conversation
            results = self.collection.get(
                where={"conversation_id": conversation_id},
            )
            if results and results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(
                    f"{len(results['ids'])} memoires supprimees pour conversation {conversation_id[:8]}"
                )
        except Exception as e:
            logger.error(f"Erreur suppression mémoire ChromaDB: {e}")

    def get_memory_stats(self) -> dict:
        """Obtenir des statistiques sur la mémoire."""
        stats = {
            "long_term_available": self.is_available,
            "long_term_enabled": settings.enable_long_term_memory,
            "total_documents": 0,
        }

        if self.is_available:
            try:
                stats["total_documents"] = self.collection.count()
            except Exception:
                pass

        return stats


# Instance globale (singleton)
memory_service = MemoryService()
