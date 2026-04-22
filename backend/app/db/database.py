"""
database.py — Configuração da sessão assíncrona PostgreSQL com SQLAlchemy.

Disponibiliza:
    - engine          : AsyncEngine (asyncpg)
    - AsyncSessionLocal: factory de sessões assíncronas
    - Base            : DeclarativeBase para todos os modelos ORM
    - get_db()        : dependência FastAPI para injecção de sessão
    - init_db()       : cria todas as tabelas no arranque (create_all)
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine assíncrono
# ---------------------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.APP_ENV == "development"),  # SQL debug apenas em dev
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # detecta ligações mortas
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ---------------------------------------------------------------------------
# Base declarativa — todos os modelos ORM herdam daqui
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependência FastAPI — injected via Depends(get_db)
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Abre uma sessão de base de dados e garante que é fechada após o pedido."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Inicialização — cria as tabelas se não existirem (chamada no startup)
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Cria todas as tabelas definidas nos modelos ORM. Idempotente."""
    # Import aqui para garantir que os modelos estão registados na Base
    from app.models import utilizador  # noqa: F401  — regista os modelos

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tabelas PostgreSQL verificadas/criadas com sucesso.")
