"""
Base de données SQLite — Gustave Code
Gestion des conversations et messages avec SQLAlchemy.
"""

import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    Integer,
    ForeignKey,
    JSON,
    event,
    text as sa_text,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    relationship,
    Session,
)

from app.config import settings

# ============================================
# Configuration Engine
# ============================================

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite nécessite ça
    echo=False,
)

# Activer WAL mode pour de meilleures performances en lecture/écriture
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()


# ============================================
# Modèles ORM
# ============================================

def generate_uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(Text, nullable=False, default="Nouvelle conversation")
    model_profile = Column(String, nullable=True, default="fast")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relation vers les messages
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    @property
    def message_count(self) -> int:
        return len(self.messages)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String, nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False, default="")
    thinking_content = Column(Text, nullable=True)  # Contenu du bloc <think>
    tool_calls = Column(JSON, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    thinking_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relation vers la conversation
    conversation = relationship("Conversation", back_populates="messages")


# ============================================
# Utilitaires de session
# ============================================

def get_db():
    """Dependency injection pour FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Session:
    """Context manager pour usage hors FastAPI."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ============================================
# Opérations CRUD
# ============================================

def create_conversation(
    db: Session,
    title: str = "Nouvelle conversation",
    model_profile: str = "quality",
) -> Conversation:
    """Créer une nouvelle conversation."""
    conv = Conversation(
        id=generate_uuid(),
        title=title,
        model_profile=model_profile,
    )
    db.add(conv)
    db.commit()
    # Note: expire_on_commit=False dans SessionLocal, pas besoin de refresh
    return conv


def get_conversation(db: Session, conversation_id: str) -> Conversation | None:
    """Récupérer une conversation par ID."""
    return db.query(Conversation).filter(Conversation.id == conversation_id).first()


def list_conversations(db: Session, limit: int = 50, offset: int = 0) -> list[Conversation]:
    """Lister les conversations, les plus récentes d'abord."""
    return (
        db.query(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def delete_conversation(db: Session, conversation_id: str) -> bool:
    """Supprimer une conversation et tous ses messages."""
    conv = get_conversation(db, conversation_id)
    if conv:
        db.delete(conv)
        db.commit()
        return True
    return False


def delete_all_conversations(db: Session) -> int:
    """Supprimer toutes les conversations et leurs messages. Retourne le nombre supprimé."""
    count = db.query(Conversation).count()
    if count > 0:
        db.query(Message).delete()
        db.query(Conversation).delete()
        db.commit()
    return count


def add_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    thinking_content: str | None = None,
    tool_calls: dict | None = None,
    extra_metadata: dict | None = None,
    tokens_used: int | None = None,
    thinking_time_ms: int | None = None,
) -> Message:
    """Ajouter un message à une conversation."""
    msg = Message(
        id=generate_uuid(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        thinking_content=thinking_content,
        tool_calls=tool_calls,
        extra_metadata=extra_metadata,
        tokens_used=tokens_used,
        thinking_time_ms=thinking_time_ms,
    )
    db.add(msg)

    # Mettre à jour updated_at de la conversation
    conv = get_conversation(db, conversation_id)
    if conv:
        conv.updated_at = datetime.now(timezone.utc)

    db.commit()
    # Note: expire_on_commit=False dans SessionLocal, pas besoin de refresh
    return msg


def get_conversation_messages(
    db: Session,
    conversation_id: str,
    limit: int | None = None,
) -> list[Message]:
    """Récupérer les messages d'une conversation."""
    query = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    if limit:
        query = query.limit(limit)
    return query.all()


def update_conversation_title(db: Session, conversation_id: str, title: str) -> bool:
    """Mettre à jour le titre d'une conversation."""
    conv = get_conversation(db, conversation_id)
    if conv:
        conv.title = title
        db.commit()
        return True
    return False


# ============================================
# Initialisation + Auto-migration
# ============================================

def _auto_migrate():
    """
    Ajoute les colonnes manquantes aux tables existantes.
    SQLAlchemy create_all ne modifie pas les tables déjà créées,
    donc on inspecte le schéma et on fait ALTER TABLE si nécessaire.
    """
    import logging
    logger = logging.getLogger("gustave-code")

    with engine.connect() as conn:
        for table_name, table in Base.metadata.tables.items():
            # Récupérer les colonnes existantes dans la DB
            result = conn.execute(
                sa_text(f"PRAGMA table_info({table_name})")
            )
            existing_cols = {row[1] for row in result}

            # Vérifier chaque colonne du modèle
            for col in table.columns:
                if col.name not in existing_cols:
                    # Déterminer le type SQL
                    col_type = col.type.compile(engine.dialect)
                    nullable = "" if col.nullable else " NOT NULL"
                    default = ""
                    if col.default is not None and col.default.is_scalar:
                        default = f" DEFAULT '{col.default.arg}'"

                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{nullable}{default}"
                    try:
                        conn.execute(sa_text(sql))
                        logger.info(f"Migration: ajout colonne {table_name}.{col.name} ({col_type})")
                    except Exception as e:
                        logger.warning(f"Migration: impossible d'ajouter {table_name}.{col.name}: {e}")

        conn.commit()


def init_db():
    """Créer toutes les tables si elles n'existent pas, puis migrer."""
    Base.metadata.create_all(bind=engine)
    _auto_migrate()
