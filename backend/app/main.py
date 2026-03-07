"""
Point d'entrée FastAPI — Gustave Code
Application principale avec lifespan, CORS et routes.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.db import init_db
from app.routers import chat, conversations, models, health

# ============================================
# Logging
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("gustave-code")


# ============================================
# Lifespan (startup / shutdown)
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisation au démarrage et nettoyage à l'arrêt."""
    # --- Startup ---
    logger.info("Demarrage de Gustave Code...")

    init_db()
    logger.info("Base de donnees SQLite initialisee")

    try:
        from app.services.memory_service import memory_service
        memory_service.initialize()
        logger.info("ChromaDB (memoire long-terme) connecte")
    except Exception as e:
        logger.warning(f"ChromaDB non disponible: {e}")

    try:
        from app.services.llm_service import llm_service
        is_connected = await llm_service.check_ollama_connection()
        if is_connected:
            logger.info("Ollama connecte")
        else:
            logger.warning("Ollama non accessible — verifiez qu'il est lance")
    except Exception as e:
        logger.warning(f"Impossible de verifier Ollama: {e}")

    logger.info(f"Fournisseur LLM: {settings.llm_provider}")
    logger.info(f"Profil par defaut: {settings.default_model_profile.value}")
    logger.info("Gustave Code est pret")

    yield

    # --- Shutdown ---
    logger.info("Arret de Gustave Code")


# ============================================
# Application FastAPI
# ============================================

app = FastAPI(
    title="Gustave Code",
    description="Assistant IA personnel local — Gustave Code",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================
# CORS
# ============================================

origins = [origin.strip() for origin in settings.cors_origins.split(",")]
# Toujours inclure 127.0.0.1 en plus de localhost
for origin in list(origins):
    if "localhost" in origin:
        origins.append(origin.replace("localhost", "127.0.0.1"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Routes
# ============================================

app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
app.include_router(models.router, prefix="/models", tags=["Models"])


@app.get("/")
async def root():
    return {
        "name": "Gustave Code",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
