"""
profile_service.py — CRUD assíncrono do perfil biográfico no PostgreSQL.

Funções:
    get_or_create_user      : busca ou cria o registo Utilizador
    get_profile             : busca o PerfilBiografico do utilizador
    save_profile            : persiste/actualiza o perfil JSON
    mark_onboarding_done    : assinala onboarding_completo = True
    add_tema_explorado      : acrescenta um tema à lista de temas explorados
    get_temas_explorados    : devolve a lista de temas já explorados
"""

from __future__ import annotations

import uuid
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilizador import Utilizador, PerfilBiografico

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilizador
# ---------------------------------------------------------------------------

async def get_or_create_user(user_id: str, db: AsyncSession) -> Utilizador:
    """
    Busca o utilizador pelo UUID. Cria-o se não existir.

    Args:
        user_id: UUID do utilizador (string).
        db:      Sessão assíncrona SQLAlchemy.

    Returns:
        Instância do modelo Utilizador.
    """
    uid = uuid.UUID(user_id)
    result = await db.execute(select(Utilizador).where(Utilizador.id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        user = Utilizador(id=uid)
        db.add(user)
        await db.flush()  # persiste sem commit para que o ID fique disponível
        logger.info("Novo utilizador criado: %s", uid)

    return user


async def is_onboarding_done(user_id: str, db: AsyncSession) -> bool:
    """Devolve True se o utilizador já completou o onboarding."""
    uid = uuid.UUID(user_id)
    result = await db.execute(select(Utilizador).where(Utilizador.id == uid))
    user = result.scalar_one_or_none()
    return bool(user and user.onboarding_completo)


async def mark_onboarding_done(user_id: str, nome: Optional[str], db: AsyncSession) -> None:
    """
    Assinala onboarding_completo = True e guarda o nome se disponível.
    """
    user = await get_or_create_user(user_id, db)
    user.onboarding_completo = True
    if nome:
        user.nome = nome
    await db.flush()
    logger.info("Onboarding concluído para utilizador %s", user_id)


# ---------------------------------------------------------------------------
# Perfil Biográfico
# ---------------------------------------------------------------------------

async def get_profile(user_id: str, db: AsyncSession) -> Optional[PerfilBiografico]:
    """Devolve o PerfilBiografico do utilizador ou None se não existir."""
    uid = uuid.UUID(user_id)
    result = await db.execute(
        select(PerfilBiografico).where(PerfilBiografico.utilizador_id == uid)
    )
    return result.scalar_one_or_none()


async def save_profile(
    user_id: str,
    perfil_json: dict,
    historico_onboarding: list[dict],
    db: AsyncSession,
) -> PerfilBiografico:
    """
    Cria ou actualiza o perfil biográfico do utilizador.

    Args:
        user_id:               UUID do utilizador.
        perfil_json:           Dicionário extraído pelo Gemini.
        historico_onboarding:  Lista de mensagens do onboarding (para referência).
        db:                    Sessão assíncrona.

    Returns:
        Instância actualizada de PerfilBiografico.
    """
    # Garante que o utilizador existe
    await get_or_create_user(user_id, db)

    perfil = await get_profile(user_id, db)

    if perfil is None:
        perfil = PerfilBiografico(
            utilizador_id=uuid.UUID(user_id),
            perfil_json=perfil_json,
            temas_explorados=[],
            historico_onboarding=historico_onboarding,
        )
        db.add(perfil)
    else:
        # Merge: actualiza apenas os campos não-nulos do novo perfil
        perfil_existente = perfil.perfil_json or {}
        for key, value in perfil_json.items():
            if value is not None:
                perfil_existente[key] = value
        perfil.perfil_json = perfil_existente
        perfil.historico_onboarding = historico_onboarding

    await db.flush()
    logger.info("Perfil guardado para utilizador %s", user_id)
    return perfil


async def add_tema_explorado(user_id: str, tema: str, db: AsyncSession) -> None:
    """
    Acrescenta um tema à lista de temas_explorados (evita duplicados).
    """
    perfil = await get_profile(user_id, db)
    if perfil is None:
        logger.warning("Tentativa de adicionar tema sem perfil existente: %s", user_id)
        return

    temas = list(perfil.temas_explorados or [])
    if tema not in temas:
        temas.append(tema)
        perfil.temas_explorados = temas
        await db.flush()
        logger.info("Tema '%s' adicionado ao utilizador %s", tema, user_id)


async def get_temas_explorados(user_id: str, db: AsyncSession) -> list[str]:
    """Devolve a lista de temas já explorados pelo utilizador."""
    perfil = await get_profile(user_id, db)
    if perfil is None:
        return []
    return list(perfil.temas_explorados or [])
