"""
onboarding_service.py — Fluxo de onboarding para o primeiro acesso do idoso.

Responsabilidades:
    1. Definir as 5 perguntas fixas de onboarding
    2. Determinar qual a próxima pergunta a fazer (com base no historico)
    3. Detectar quando o onboarding está completo (todas respondidas)
    4. Extrair o perfil biográfico JSON usando Gemini 2.5 Flash
"""

from __future__ import annotations

import json
import logging

from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cliente Groq para extração (substitui Gemini em modo de teste)
# ---------------------------------------------------------------------------
_groq_client: Groq | None = None

def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client

# ---------------------------------------------------------------------------
# Perguntas fixas de onboarding (apresentadas apenas na 1.ª sessão)
# ---------------------------------------------------------------------------
PERGUNTAS_ONBOARDING: list[str] = [
    "Como se chama e onde nasceu?",
    "Tem filhos ou netos? Conte-me da sua família.",
    "A que se dedicou a maior parte da sua vida?",
    "Viveu sempre na mesma terra ou mudou-se?",
    "Qual o momento da sua vida que mais gosta de recordar?",
]

# ---------------------------------------------------------------------------
# Mensagem de abertura (antes da 1.ª pergunta)
# ---------------------------------------------------------------------------
BOAS_VINDAS = (
    "Olá! Sou o Memórias Vivas, o seu assistente de conversação. "
    "Antes de começarmos, gostava de o/a conhecer um pouco melhor. "
    "Vou fazer-lhe algumas perguntas curtas. Fique à vontade para responder "
    "como quiser — não há respostas certas ou erradas. Está pronto/a?"
)


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def get_boas_vindas() -> str:
    """Devolve a mensagem de boas-vindas para o 1.º acesso."""
    return BOAS_VINDAS


def get_next_question(historico: list[dict]) -> str | None:
    """
    Devolve a próxima pergunta de onboarding que ainda não foi colocada.

    Args:
        historico: Lista de mensagens [{role, content}, ...] da sessão de onboarding.

    Returns:
        Próxima pergunta (str) ou None se todas já foram feitas.
    """
    # Conta quantas perguntas do assistente já estão no histórico
    perguntas_feitas = [
        msg["content"]
        for msg in historico
        if msg.get("role") == "assistant"
        and msg.get("content") in PERGUNTAS_ONBOARDING
    ]
    feitas_set = set(perguntas_feitas)

    for pergunta in PERGUNTAS_ONBOARDING:
        if pergunta not in feitas_set:
            return pergunta

    return None  # todas as perguntas já foram feitas


def is_onboarding_complete(historico: list[dict]) -> bool:
    """
    Retorna True quando todas as perguntas de onboarding foram feitas
    E o utilizador respondeu à última.
    """
    perguntas_feitas = [
        msg["content"]
        for msg in historico
        if msg.get("role") == "assistant"
        and msg.get("content") in PERGUNTAS_ONBOARDING
    ]
    todas_feitas = all(p in set(perguntas_feitas) for p in PERGUNTAS_ONBOARDING)

    if not todas_feitas:
        return False

    # Garante que há uma resposta do utilizador após a última pergunta do assistente
    ultima_msg = historico[-1] if historico else {}
    return ultima_msg.get("role") == "user"


# ---------------------------------------------------------------------------
# Extração de perfil com Gemini 2.5 Flash
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """
Analisa a conversa de onboarding abaixo e extrai o perfil biográfico do idoso em JSON.
Devolve APENAS o JSON, sem explicações, sem markdown.

Schema obrigatório (preenche com o que foi mencionado, usa null se não disponível):
{{
  "nome": "string ou null",
  "terra_natal": "string ou null",
  "familia": "string descritiva ou null",
  "profissao": "string ou null",
  "memoria_marcante": "string ou null",
  "outros": {{}}
}}

Conversa de onboarding:
{conversa}
"""


async def extract_profile_with_gemini(historico: list[dict]) -> dict:
    """
    Extrai o perfil biográfico JSON da conversa de onboarding via Groq/Llama.
    (Substituição do Gemini para testes — evita quotas e problemas de modelo.)
    """
    conversa_texto = "\n".join(
        f"{'Assistente' if msg['role'] == 'assistant' else 'Idoso'}: {msg['content']}"
        for msg in historico
    )

    prompt = _EXTRACTION_PROMPT.format(conversa=conversa_texto)

    _EMPTY = {
        "nome": None, "terra_natal": None, "familia": None,
        "profissao": None, "memoria_marcante": None, "outros": {},
    }

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        resposta = await loop.run_in_executor(
            None,
            lambda: _get_groq().chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "És um extractor de perfis biográficos. "
                            "Respondes APENAS com JSON válido, sem texto adicional nem blocos de código. "
                            "Segue exatamente o schema pedido."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=512,
            ),
        )
        raw = resposta.choices[0].message.content.strip()
        # Limpar possíveis blocos de código que o modelo inclua
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        perfil = json.loads(raw.strip())
        logger.info("Groq extraiu perfil com sucesso: %s", list(perfil.keys()))
        return perfil

    except json.JSONDecodeError as exc:
        logger.error("Groq devolveu JSON inválido na extração: %s", exc)
        return _EMPTY
    except Exception as exc:
        logger.error("Erro ao chamar Groq para extração de perfil: %s", exc)
        raise