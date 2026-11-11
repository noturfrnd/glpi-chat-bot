"""Configuração do banco assíncrono e modelo de histórico do chat."""

from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import (
    Column,
    JSON,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Resolve o arquivo a partir deste módulo, independentemente do diretório de execução.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = f"sqlite+aiosqlite:///{(PROJECT_ROOT / 'database.db').as_posix()}"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Classe base para os modelos SQLAlchemy da aplicação."""


class ChatMessage(Base):
    """Mensagem individual associada a uma conversa persistente."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


CACHE_DOMAINS = ("account", "users", "tickets", "articles", "categories", "timeline")
CACHE_TABLES = {
    domain: Table(
        f"cache_{domain}",
        Base.metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("source_key", String(255), nullable=True),
        Column("data", JSON, nullable=False),
        UniqueConstraint("source_key", name=f"uq_cache_{domain}_source_key"),
    )
    for domain in CACHE_DOMAINS
}


async def init_db() -> None:
    """Cria as tabelas mapeadas que ainda não existem."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Fornece uma sessão por operação e a fecha ao terminar."""
    async with AsyncSessionLocal() as session:
        yield session
