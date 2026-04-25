"""
app/services/redis_service.py — Gestão de histórico de sessão com Redis.

Responsabilidades:
    - Pool de ligações assíncrono (singleton, inicializado no lifespan).
    - get_historico()     → recupera o histórico de uma sessão.
    - set_historico()     → persiste o histórico completo.
    - append_interacao()  → adiciona um par user/assistant e persiste.
    - delete_historico()  → limpa a sessão (chamado no encerramento → Gemini).
    - session_exists()    → verifica se uma sessão já existe.

TTL padrão: 24 horas (SESSION_TTL_SECONDS).
Prefixo de chaves: "mv:session:hist:<session_id>"
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
SESSION_TTL_SECONDS: int = 60 * 60 * 24    # 24 horas
_HIST_PREFIX = "mv:session:hist:"           # namespace explícito no Redis

# ---------------------------------------------------------------------------
# Pool de ligações — singleton, partilhado por todos os pedidos
# ---------------------------------------------------------------------------
_redis_pool: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """
    Cria o pool de ligações ao Redis.
    Chamado UMA VEZ no lifespan do FastAPI (startup).
    """
    global _redis_pool
    if _redis_pool is not None:
        return  # já inicializado — idempotente

    url = settings.REDIS_URL   # ex: "redis://redis:6379/0"
    logger.info("A ligar ao Redis: %s", url)

    _redis_pool = aioredis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=10,
    )

    # Verificação de conectividade no arranque
    await _redis_pool.ping()
    logger.info("Redis ligado com sucesso.")


async def close_redis() -> None:
    """
    Encerra o pool de ligações.
    Chamado no shutdown do FastAPI.
    """
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Ligação ao Redis encerrada.")


def _get_pool() -> aioredis.Redis:
    """Devolve o pool ativo ou lança erro claro se não foi inicializado."""
    if _redis_pool is None:
        raise RuntimeError(
            "Redis não inicializado. "
            "Garante que init_redis() é chamado no lifespan da aplicação."
        )
    return _redis_pool


def _key(session_id: str) -> str:
    """Constrói a chave Redis com prefixo de namespace."""
    return f"{_HIST_PREFIX}{session_id}"


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

async def get_historico(session_id: str) -> list[dict]:
    """
    Recupera o histórico de mensagens de uma sessão.

    Returns:
        Lista de dicts {"role": "user"|"assistant", "content": str}.
        Lista vazia se a sessão não existir (sessão nova).
    """
    raw = await _get_pool().get(_key(session_id))
    if raw is None:
        logger.debug("Sessão nova iniciada: %s", session_id)
        return []

    historico: list[dict] = json.loads(raw)
    logger.debug(
        "Histórico recuperado | sessão=%s | mensagens=%d",
        session_id, len(historico),
    )
    return historico


async def set_historico(
    session_id: str,
    historico: list[dict],
    ttl: int = SESSION_TTL_SECONDS,
) -> None:
    """
    Persiste o histórico completo de uma sessão, renovando o TTL.

    Args:
        session_id: Identificador único da sessão.
        historico:  Lista de mensagens no formato {"role", "content"}.
        ttl:        Tempo de vida em segundos (padrão 24h).
    """
    await _get_pool().setex(
        _key(session_id),
        ttl,
        json.dumps(historico, ensure_ascii=False),
    )
    logger.debug(
        "Histórico guardado | sessão=%s | mensagens=%d | ttl=%ds",
        session_id, len(historico), ttl,
    )


async def append_interacao(
    session_id: str,
    user_msg: str,
    assistant_msg: str,
    ttl: int = SESSION_TTL_SECONDS,
) -> list[dict]:
    """
    Adiciona um par user/assistant ao histórico e persiste no Redis.

    Padrão: get → append → set.
    Renova automaticamente o TTL a cada interação (sessão ativa = TTL reiniciado).

    Returns:
        Histórico completo atualizado.
    """
    historico = await get_historico(session_id)
    historico.append({"role": "user",      "content": user_msg})
    historico.append({"role": "assistant", "content": assistant_msg})
    await set_historico(session_id, historico, ttl)
    return historico


async def delete_historico(session_id: str) -> bool:
    """
    Remove o histórico de uma sessão do Redis.
    Deve ser chamado em POST /sessao/encerrar antes de invocar o Gemini
    para extração do perfil biográfico (Epic 3.3).

    Returns:
        True se a chave existia e foi removida, False se já não existia.
    """
    deleted = await _get_pool().delete(_key(session_id))
    logger.info(
        "Histórico eliminado | sessão=%s | existia=%s",
        session_id, bool(deleted),
    )
    return bool(deleted)


async def session_exists(session_id: str) -> bool:
    """
    Verifica se uma sessão já existe no Redis.
    Útil para distinguir sessões novas de sessões retomadas no endpoint.
    """
    return bool(await _get_pool().exists(_key(session_id)))