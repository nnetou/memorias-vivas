"""
onboarding_service.py — Onboarding conversacional conduzido pelo Groq.

Abordagem:
    Em vez de 5 perguntas fixas, o Groq conduz uma conversa natural
    com o idoso, recolhendo as informações necessárias ao perfil.

    O modelo decide:
      - Como formular cada pergunta (calorosa, em PT-PT)
      - Quando usar o nome e pronome correto (Sr./Sra.)
      - Se a resposta faz sentido no contexto (validação implícita)
      - Quando tem informação suficiente para encerrar

    Quando o Groq considera o onboarding completo, devolve a tag
    especial [ONBOARDING_COMPLETO] no início da mensagem.
    O backend deteta esta tag e extrai o perfil.

Informação a recolher (não tem de seguir esta ordem):
    - Nome completo e idade aproximada
    - Localidade onde vive (Portugal ou região)
    - Família (filhos, netos, estado civil)
    - Profissão ou ocupação principal
    - Uma memória ou momento marcante da vida
"""

from __future__ import annotations

import json
import logging
import re

from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cliente Groq
# ---------------------------------------------------------------------------

_client: Groq | None = None

def _get_groq() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# System prompt do onboarding conversacional
# ---------------------------------------------------------------------------

SYSTEM_ONBOARDING = """O teu nome é Raquel. Tens conversas calorosas e naturais com pessoas idosas, em Português de Portugal (PT-PT).

APRESENTAÇÃO OBRIGATÓRIA: Quando te apresentares, diz apenas o teu nome. Nunca menciones "projeto", "assistente", "aplicação" nem qualquer contexto técnico. Apresenta-te de forma simples: "Olá, chamo-me Raquel." — nada mais.

OBJETIVO: Recolher as seguintes informações ao longo da conversa:
  1. Nome completo e idade aproximada
  2. Localidade onde vive (deve ser em Portugal — se disser outro país, pede gentilmente para confirmar)
  3. Família (filhos, netos, estado civil)
  4. Profissão ou ocupação principal (atual ou passada)
  5. Uma memória ou momento marcante da vida

REGRAS OBRIGATÓRIAS:
- Na apresentação, diz apenas o teu nome — nada mais sobre quem és.
- Faz SEMPRE apenas UMA pergunta de cada vez.
- Após a primeira resposta, identifica o nome e o género e trata a pessoa por "o senhor" ou "a senhora" — NUNCA uses "você" (é uma expressão brasileira).
- Fala SEMPRE em Português de Portugal (PT-PT). É absolutamente proibido usar expressões brasileiras: "você", "tá", "né", "legal", "bacana", "ótimo".
- Se uma resposta não fizer sentido no contexto português, pede gentilmente para confirmar, sem ser condescendente.
- Se uma resposta for vaga, aceita e avança — não insistas.
- Usa linguagem simples, frases curtas e tom paciente e caloroso.
- Quando tiveres informação suficiente sobre os 5 pontos, termina com uma frase calorosa de agradecimento.
- Quando terminares, coloca EXATAMENTE no início da mensagem a tag: [ONBOARDING_COMPLETO]
- Nunca uses emojis.
"""

# Máximo de trocas antes de forçar o encerramento
MAX_TROCAS = 14


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def get_boas_vindas() -> str:
    """Primeira mensagem do assistente — gerada pelo Groq."""
    resposta = _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_ONBOARDING},
            {"role": "user",   "content": "Olá"},
        ],
        temperature=0.7,
        max_tokens=200,
    )
    return resposta.choices[0].message.content.strip()


def proxima_mensagem(historico: list[dict]) -> str:
    """
    Dada a conversa até agora, o Groq gera a próxima mensagem do assistente.
    Pode ser uma pergunta ou, quando tiver informação suficiente,
    uma mensagem de conclusão com [ONBOARDING_COMPLETO].
    """
    # Forçar encerramento se demasiadas trocas
    mensagens = [{"role": "system", "content": SYSTEM_ONBOARDING}]

    n_trocas = sum(1 for m in historico if m["role"] == "user")
    if n_trocas >= MAX_TROCAS:
        mensagens.append({
            "role": "system",
            "content": "Já recolheste informação suficiente. Encerra agora com [ONBOARDING_COMPLETO]."
        })

    mensagens.extend(historico)

    resposta = _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.7,
        max_tokens=300,
    )
    return resposta.choices[0].message.content.strip()


def is_onboarding_complete(mensagem_assistente: str) -> bool:
    """Verifica se a mensagem contém a tag de conclusão."""
    return "[ONBOARDING_COMPLETO]" in mensagem_assistente


def limpar_tag(mensagem: str) -> str:
    """Remove a tag [ONBOARDING_COMPLETO] da mensagem para mostrar ao utilizador."""
    return mensagem.replace("[ONBOARDING_COMPLETO]", "").strip()


# ---------------------------------------------------------------------------
# Extração de perfil — Gemini 2.5 Flash (Epic 3.2)
# ---------------------------------------------------------------------------

async def extract_profile_with_gemini(historico: list[dict]) -> dict:
    """
    Extrai o perfil biográfico rico da conversa de onboarding via Gemini 2.5 Flash.

    Usa o gemini_service que aplica response_mime_type="application/json" para
    garantir JSON válido. O schema rico inclui pessoas, locais, datas, eventos,
    tradições e expressões regionais (Epic 3.1).

    Em caso de falha do Gemini, faz fallback para extração via Groq.

    Args:
        historico: Lista de mensagens {"role": str, "content": str}.

    Returns:
        Dict com o perfil biográfico (schema rico compatível com o simples).
    """
    from app.services.gemini_service import extrair_perfil as _gemini_extrair

    # Tentativa principal: Gemini 2.5 Flash
    try:
        logger.info("Extração de perfil via Gemini 2.5 Flash...")
        perfil = await _gemini_extrair(historico)
        logger.info("Perfil extraído pelo Gemini | campos: %s", list(perfil.keys()))
        return perfil

    except Exception as exc:
        logger.warning(
            "Gemini indisponível (%s) — a usar Groq como fallback para extração.",
            exc,
        )

    # Fallback: Groq (Llama 3.3 70B) com schema simplificado
    import asyncio

    _EXTRACTION_PROMPT = """\
Analisa a conversa abaixo com um idoso em Portugal e extrai o perfil biográfico detalhado no seguinte formato JSON.
Devolve APENAS o JSON válido, sem qualquer introdução, explicação ou blocos markdown.

Schema JSON (usa null ou arrays vazios [] quando não houver informação correspondente):
{{
  "nome": null,
  "terra_natal": null,
  "familia": null,
  "profissao": null,
  "memoria_marcante": null,
  "pessoas": [],
  "locais": [],
  "datas_aproximadas": [],
  "eventos_marcantes": [],
  "tradicoes": [],
  "expressoes_regionais": [],
  "momentos_chave": [],
  "linha_temporal": [
    {{
      "periodo": "Ex: 10 anos, 1970, ou infância",
      "acontecimento": "Descrição breve do acontecimento"
    }}
  ],
  "memorias": [
    {{
      "titulo": "Título evocativo curto",
      "narrativa": "Narrativa curta de 50-80 palavras em prosa, na 3ª pessoa.",
      "pessoas_envolvidas": [],
      "local": null,
      "emocao": null,
      "idade_ou_data": null
    }}
  ],
  "resumo_narrativo": null,
  "outros": {{}}
}}

Conversa:
{conversa}
"""
    conversa = "\n".join(
        f"{'Assistente' if m['role'] == 'assistant' else 'Idoso'}: {m['content']}"
        for m in historico
        if isinstance(m, dict) and "role" in m and "content" in m
    )

    loop = asyncio.get_event_loop()
    try:
        resposta = await loop.run_in_executor(
            None,
            lambda: _get_groq().chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "És um extractor de perfis biográficos. "
                            "Respondes APENAS com JSON válido, sem texto adicional nem blocos de código."
                        ),
                    },
                    {"role": "user", "content": _EXTRACTION_PROMPT.format(conversa=conversa)},
                ],
                temperature=0.1,
                max_tokens=512,
            ),
        )
        raw = resposta.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        perfil = json.loads(raw.strip())
        from app.services.gemini_service import _PERFIL_VAZIO
        perfil_rico = dict(_PERFIL_VAZIO)
        for k, v in perfil.items():
            perfil_rico[k] = v
        logger.info("Perfil extraído (fallback Groq): %s", list(perfil_rico.keys()))
        return perfil_rico

    except json.JSONDecodeError as exc:
        logger.error("Fallback Groq | JSON inválido na extração: %s", exc)
        return {
            "nome": None, "terra_natal": None, "familia": None,
            "profissao": None, "memoria_marcante": None,
            "pessoas": [], "locais": [], "datas_aproximadas": [],
            "eventos_marcantes": [], "tradicoes": [], "expressoes_regionais": [],
            "momentos_chave": [], "linha_temporal": [], "memorias": [],
            "resumo_narrativo": None, "outros": {},
        }
    except Exception as exc:
        logger.error("Fallback Groq | Erro na extração de perfil: %s", exc)
        raise