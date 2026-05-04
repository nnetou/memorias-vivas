"""
main.py — Ponto de entrada da aplicação FastAPI Memórias Vivas.

Startup:
    - init_db(): cria as tabelas PostgreSQL se não existirem
    - init_redis(): inicializa o pool de ligações ao Redis

Shutdown:
    - close_redis(): encerra o pool de ligações ao Redis
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import chat, audio, ws, auth

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup e shutdown gerenciados com asynccontextmanager
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa recursos no arranque e liberta-os no shutdown."""

    # ── Startup ─────────────────────────────────────────────────────────────
    logger.info("A iniciar Memórias Vivas API (env=%s)...", settings.APP_ENV)

    # PostgreSQL
    if settings.DATABASE_URL:
        from app.db.database import init_db
        await init_db()
    else:
        logger.warning("DATABASE_URL não configurada — tabelas não criadas.")

    # Redis — memória curta de sessão (Epic 4.1)
    if settings.REDIS_URL:
        from app.services.redis_service import init_redis
        await init_redis()
    else:
        logger.warning("REDIS_URL não configurada — histórico de sessão não persistido.")

    yield  # ── a aplicação corre aqui ────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if settings.REDIS_URL:
        from app.services.redis_service import close_redis
        await close_redis()

    logger.info("Memórias Vivas API encerrada.")


# ---------------------------------------------------------------------------
# Aplicação FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,  prefix="/api/v1/auth",  tags=["Autenticação"])
app.include_router(chat.router,  prefix="/api/v1/chat",  tags=["Chat"])
app.include_router(audio.router, prefix="/api/v1/audio", tags=["Voz"])
app.include_router(ws.router,    prefix="/api/v1/audio/ws", tags=["Voz — WebSocket"])


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Sistema"])
async def health_check():
    """Verifica o estado de saúde da API."""
    return {
        "status": "ok",
        "projeto": settings.PROJECT_NAME,
        "versao": settings.VERSION,
        "ambiente": settings.APP_ENV,
        "chaves": {
            "groq": bool(settings.GROQ_API_KEY),
            "google": bool(settings.GOOGLE_API_KEY),
            "database": bool(settings.DATABASE_URL),
            "redis": bool(settings.REDIS_URL),
        },
    }