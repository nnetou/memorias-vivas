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
    Consentimento, PerfilBiografico, RoleEnum, Utilizador, Sessao
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
        "perfil": {
            "nome":             "Ana Costa",
            "terra_natal":      "Lisboa",
            "familia":          "Casada, mãe de dois filhos.",
            "profissao":        "Enfermeira e cuidadora de idosos.",
            "memoria_marcante": "A primeira vez que ajudou a recuperar a memória de um utente.",
            "linha_temporal": [
                {"periodo": "18 anos", "acontecimento": "Entrou na Escola Superior de Enfermagem de Lisboa."},
                {"periodo": "22 anos", "acontecimento": "Terminou a licenciatura e começou a trabalhar num hospital público."},
                {"periodo": "28 anos", "acontecimento": "Casou-se e mudou-se para uma casa perto da praia."},
                {"periodo": "35 anos", "acontecimento": "Decidiu focar-se inteiramente no cuidado de idosos e preservação de memórias."}
            ],
            "outros": {
                "hobbies": "Fotografia documental, leitura de biografias."
            }
        },
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
            "linha_temporal": [
                {"periodo": "10 anos", "acontecimento": "Começou a ajudar o pai na oficina de carpintaria em Évora."},
                {"periodo": "18 anos", "acontecimento": "Ganhou o seu primeiro ordenado a sério e comprou uma bicicleta."},
                {"periodo": "21 anos", "acontecimento": "Foi chamado para a tropa e esteve destacado nos Açores."},
                {"periodo": "25 anos", "acontecimento": "Casou-se com a sua esposa Maria na Sé de Évora."},
                {"periodo": "28 anos", "acontecimento": "Nascimento do seu primeiro filho, o João."},
                {"periodo": "31 anos", "acontecimento": "Nascimento da sua filha Ana."},
                {"periodo": "45 anos", "acontecimento": "Abriu a sua própria oficina de carpintaria no centro da cidade."},
                {"periodo": "65 anos", "acontecimento": "Reformou-se após 40 anos dedicados à arte da carpintaria."}
            ],
            "memorias": [
                {
                    "titulo": "A Primeira Bicicleta",
                    "narrativa": "Manuel lembra-se com muita alegria do dia em que, aos 18 anos, juntou o seu primeiro ordenado para comprar uma bicicleta pasteleira preta. Com ela, começou a ir todos os dias de Évora até à aldeia vizinha para visitar a Maria, que mais tarde viria a ser sua esposa.",
                    "pessoas_envolvidas": ["Manuel", "Maria"],
                    "local": "Évora",
                    "emocao": "Alegria",
                    "idade_ou_data": "18 anos"
                },
                {
                    "titulo": "O Tempo da Tropa nos Açores",
                    "narrativa": "Aos 21 anos, Manuel foi destacado para os Açores. Sente muita saudade desse tempo, pois nunca tinha saído do Alentejo. O verde das ilhas e a camaradagem com os outros soldados deixaram uma marca profunda, embora sentisse falta da família.",
                    "pessoas_envolvidas": ["Manuel", "Camaradas"],
                    "local": "Açores",
                    "emocao": "Saudade",
                    "idade_ou_data": "21 anos"
                },
                {
                    "titulo": "A Inauguração da Oficina",
                    "narrativa": "Aos 45 anos, com a ajuda dos filhos João e Ana, Manuel abriu finalmente a sua própria oficina de carpintaria. O cheiro a serradura fresca e o orgulho de ver a placa com o seu nome na porta é algo que jamais esquecerá.",
                    "pessoas_envolvidas": ["Manuel", "João", "Ana"],
                    "local": "Centro de Évora",
                    "emocao": "Orgulho",
                    "idade_ou_data": "45 anos"
                }
            ],
            "outros": {
                "hobbies":      "Caminhadas pela Ribeira, jardinagem.",
                "curiosidade":  "A filha Ana começou a aprender marcenaria.",
            },
        },
        "sessoes": [
            {
                "tema": "memorias",
                "resumo": "O Sr. Manuel partilhou a sua história de juventude, revelando que aos 18 anos comprou a sua primeira bicicleta com o seu primeiro ordenado. Contou com muito entusiasmo que usava a bicicleta para ir de Évora até à aldeia vizinha, pedalando quilómetros apenas para ver a Maria, com quem viria a casar."
            },
            {
                "tema": "familia",
                "resumo": "Durante a conversa sobre família, o Manuel recordou com muito orgulho o dia em que abriu a sua própria carpintaria, já com 45 anos. Mencionou que os filhos, João e Ana, estiveram presentes e o ajudaram a montar tudo, sendo este um dos momentos de maior união familiar da sua vida."
            },
            {
                "tema": "saude",
                "resumo": "O Manuel falou sobre o seu tempo de juventude nos Açores, aos 21 anos, durante a tropa. Disse que o ar puro e as caminhadas pelas ilhas lhe deram uma saúde de ferro. Sente saudades do verde intenso da paisagem, um contraste enorme com o Alentejo onde nasceu."
            }
        ]
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
                logger.info("🔄  A atualizar: %s", dados["email"])
                existente.nome = dados["nome"]
                existente.role = dados["role"]
                existente.onboarding_completo = dados["onboarding_completo"]

                if dados["perfil"]:
                    from sqlalchemy import select
                    res_perfil = await db.execute(
                        select(PerfilBiografico).where(PerfilBiografico.utilizador_id == existente.id)
                    )
                    perfil_existente = res_perfil.scalar_one_or_none()
                    if perfil_existente:
                        perfil_existente.perfil_json = dados["perfil"]
                    else:
                        perfil = PerfilBiografico(
                            utilizador_id=existente.id,
                            perfil_json=dados["perfil"],
                            temas_explorados=["memorias", "familia"],
                        )
                        db.add(perfil)
                criados += 1
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

            # Criar sessões
            if "sessoes" in dados:
                for idx, s in enumerate(dados["sessoes"]):
                    sessao = Sessao(
                        utilizador_id=utilizador.id,
                        tema=s["tema"],
                        resumo_sessao=s["resumo"],
                    )
                    db.add(sessao)

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