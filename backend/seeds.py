"""
seeds.py — Dados de teste para o projeto Memórias Vivas.

Cria 3 utilizadores de teste com perfis e consentimentos.
Seguro para correr múltiplas vezes — ignora registos já existentes.

Uso:
    docker exec memorias_vivas_api python seeds.py
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.utilizador import (
    Consentimento, PerfilBiografico, RoleEnum, Utilizador,
)
from app.services.auth_service import hash_password

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dados de teste
# ---------------------------------------------------------------------------

UTILIZADORES = [
    {
        "email":    "admin@memoriasvivas.pt",
        "password": "Admin123",
        "nome":     "Administrador",
        "role":     RoleEnum.administrador,
        "onboarding_completo": True,
        "perfil": None,
    },
    {
        "email":    "cuidador@memoriasvivas.pt",
        "password": "Cuidador123",
        "nome":     "Ana Costa",
        "role":     RoleEnum.cuidador,
        "onboarding_completo": True,
        "perfil": None,
    },
    {
        "email":    "manuel@memoriasvivas.pt",
        "password": "Manuel123",
        "nome":     "Manuel Silva",
        "role":     RoleEnum.idoso,
        "onboarding_completo": True,
        "perfil": {
            "nome":             "Manuel Silva",
            "terra_natal":      "Évora",
            "familia":          "Dois filhos: João e Ana. A Ana mora em Évora.",
            "profissao":        "Carpinteiro durante 40 anos, reformado há 5 anos.",
            "memoria_marcante": "O dia em que o filho João nasceu.",
            "outros": {
                "hobbies":      "Caminhadas pela Ribeira, jardinagem.",
                "curiosidade":  "A filha Ana começou a aprender marcenaria.",
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Engine síncrono para seeds (usa asyncpg como o resto da app)
# ---------------------------------------------------------------------------

engine = create_async_engine(settings.DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# Seed principal
# ---------------------------------------------------------------------------

async def seed() -> None:
    async with SessionLocal() as db:
        criados = 0
        ignorados = 0

        for dados in UTILIZADORES:
            # Verificar se já existe
            from sqlalchemy import select
            resultado = await db.execute(
                select(Utilizador).where(Utilizador.email == dados["email"])
            )
            existente = resultado.scalar_one_or_none()

            if existente:
                logger.info("⏭  Já existe: %s", dados["email"])
                ignorados += 1
                continue

            # Criar utilizador
            utilizador = Utilizador(
                email=dados["email"],
                password_hash=hash_password(dados["password"]),
                nome=dados["nome"],
                role=dados["role"],
                is_active=True,
                onboarding_completo=dados["onboarding_completo"],
            )
            db.add(utilizador)
            await db.flush()  # gera o UUID

            # Criar perfil biográfico (só para o idoso)
            if dados["perfil"]:
                perfil = PerfilBiografico(
                    utilizador_id=utilizador.id,
                    perfil_json=dados["perfil"],
                    temas_explorados=["memorias", "familia"],
                    historico_onboarding=[
                        {"role": "assistant", "content": "Como se chama e onde nasceu?"},
                        {"role": "user",      "content": "Chamo-me Manuel Silva e nasci em Évora."},
                        {"role": "assistant", "content": "Tem filhos ou netos?"},
                        {"role": "user",      "content": "Tenho dois filhos, o João e a Ana."},
                        {"role": "assistant", "content": "A que se dedicou a maior parte da sua vida?"},
                        {"role": "user",      "content": "Fui carpinteiro durante 40 anos."},
                        {"role": "assistant", "content": "Viveu sempre na mesma terra?"},
                        {"role": "user",      "content": "Vivi sempre em Évora, nunca me mudei."},
                        {"role": "assistant", "content": "Qual o momento que mais gosta de recordar?"},
                        {"role": "user",      "content": "O dia em que o meu filho nasceu."},
                    ],
                )
                db.add(perfil)

            # Criar consentimento
            consentimento = Consentimento(
                utilizador_id=utilizador.id,
                autoriza_gravacao_voz=True,
                autoriza_processamento_ia=True,
                autoriza_geracao_video=False,
            )
            db.add(consentimento)

            logger.info("✅ Criado: %s (%s)", dados["email"], dados["role"].value)
            criados += 1

        await db.commit()

    logger.info("")
    logger.info("═══════════════════════════════════════")
    logger.info("Seeds concluídas: %d criados, %d ignorados", criados, ignorados)
    logger.info("═══════════════════════════════════════")
    logger.info("")
    logger.info("Credenciais de teste:")
    for u in UTILIZADORES:
        logger.info("  %s | %s | password: %s", u["role"].value.ljust(14), u["email"], u["password"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(seed())