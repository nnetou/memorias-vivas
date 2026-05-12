"""
app/services/gemini_service.py — Integração com Gemini 2.5 Flash (Epic 3.2).

Usa o SDK oficial google-genai (v1+), que substituiu o depreciado google-generativeai.

Responsabilidades:
    extrair_perfil(historico)         → extrai perfil biográfico rico (JSON estruturado)
    gerar_resumo_narrativo(historico) → gera resumo narrativo de 1-2 parágrafos (PT-PT)
    fundir_perfis(antigo, novo)       → merge inteligente de dois perfis biográficos

Schema rico do perfil (Epic 3.1 — PerfilBiografico):
    {
        "nome":                str | null,
        "terra_natal":         str | null,
        "familia":             str | null,
        "profissao":           str | null,
        "memoria_marcante":    str | null,
        "pessoas":             list[str],
        "locais":              list[str],
        "datas_aproximadas":   list[str],
        "eventos_marcantes":   list[str],
        "tradicoes":           list[str],
        "expressoes_regionais":list[str],
        "momentos_chave":      list[str],
        "resumo_narrativo":    str | null,
        "outros":              dict
    }

Notas de implementação:
    - O SDK google-genai é síncrono → usa loop.run_in_executor para não
      bloquear o event loop do FastAPI.
    - response_mime_type="application/json" força o Gemini a responder com JSON
      válido, eliminando blocos markdown na resposta.
    - Fallback robusto: em caso de falha, devolve perfil vazio em vez de lançar
      exceção — o sistema continua a funcionar com dados parciais.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types as genai_types

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração do cliente Gemini (lazy init singleton)
# ---------------------------------------------------------------------------

_client: genai.Client | None = None

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODEL = "gemini-2.0-flash"  # usado quando o 2.5 retorna 503


def _get_client() -> genai.Client:
    """Devolve o cliente Gemini (singleton, inicializado na primeira chamada)."""
    global _client
    if _client is None:
        if not settings.GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY não está definida no ficheiro .env — "
                "a extração Gemini não está disponível."
            )
        _client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _client


def _generate_with_fallback(
    contents: str,
    config: genai_types.GenerateContentConfig,
) -> genai_types.GenerateContentResponse:
    """
    Tenta gerar conteúdo com gemini-2.5-flash.
    Se receber 503 (serviço sobrecarregado), tenta gemini-2.0-flash automaticamente.
    """
    from google.genai import errors as genai_errors
    client = _get_client()
    try:
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
    except (genai_errors.ServerError, genai_errors.ClientError) as exc:
        # Verifica 503 pelo código presente na mensagem de erro
        err_str = str(exc)
        if "503" in err_str or "UNAVAILABLE" in err_str:
            logger.warning(
                "Gemini %s indisponível (503) — a usar %s como fallback.",
                GEMINI_MODEL, GEMINI_FALLBACK_MODEL,
            )
            return client.models.generate_content(
                model=GEMINI_FALLBACK_MODEL,
                contents=contents,
                config=config,
            )
        raise


# ---------------------------------------------------------------------------
# Schema vazio — devolto em caso de falha
# ---------------------------------------------------------------------------

_PERFIL_VAZIO: dict[str, Any] = {
    "nome": None,
    "terra_natal": None,
    "familia": None,
    "profissao": None,
    "memoria_marcante": None,
    "pessoas": [],
    "locais": [],
    "datas_aproximadas": [],
    "eventos_marcantes": [],
    "tradicoes": [],
    "expressoes_regionais": [],
    "momentos_chave": [],
    "resumo_narrativo": None,
    "outros": {},
}


# ---------------------------------------------------------------------------
# Prompt de extração de perfil (Epic 3.1 + 3.2)
# ---------------------------------------------------------------------------

_PROMPT_EXTRACAO = """\
Analisa a conversa de onboarding/sessão abaixo entre um assistente e um idoso português.
Extrai o perfil biográfico completo em JSON, seguindo EXATAMENTE o schema fornecido.

REGRAS:
- Usa null para campos sem informação disponível.
- Listas vazias [] se não houver itens para esse campo.
- Preserva nomes próprios, localidades e expressões exatamente como foram mencionados.
- Datas aproximadas: usa formatos como "anos 60", "1975", "infância", "juventude".
- Expressões regionais: palavras ou expressões típicas do dialeto/região do idoso.
- resumo_narrativo: 1-2 parágrafos em PT-PT fluido e caloroso, na 3ª pessoa,
  descrevendo quem é esta pessoa com base na conversa.
- Responde APENAS com o JSON, sem texto adicional, sem blocos markdown.

SCHEMA (devolve este objeto preenchido):
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
  "resumo_narrativo": null,
  "outros": {{}}
}}

CONVERSA:
{conversa}
"""


def _historico_para_texto(historico: list[dict]) -> str:
    """Converte o histórico de mensagens em texto legível para o Gemini."""
    linhas = []
    for msg in historico:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if role == "assistant":
            prefixo = "Assistente"
        elif role == "user":
            prefixo = "Idoso"
        else:
            prefixo = role.capitalize()
        linhas.append(f"{prefixo}: {content}")
    return "\n".join(linhas)


def _clean_json_response(raw: str) -> str:
    """Remove blocos markdown do JSON caso o modelo os inclua mesmo assim."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


# ---------------------------------------------------------------------------
# API pública — extrair_perfil
# ---------------------------------------------------------------------------

def _extrair_perfil_sync(historico_texto: str) -> dict:
    """
    Versão síncrona da extração — corre num thread executor para não bloquear
    o event loop do FastAPI.
    """
    prompt = _PROMPT_EXTRACAO.format(conversa=historico_texto)
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
        max_output_tokens=2048,
    )

    resposta = _generate_with_fallback(prompt, config)
    raw = _clean_json_response(resposta.text)
    perfil = json.loads(raw)

    for campo, valor_default in _PERFIL_VAZIO.items():
        if campo not in perfil:
            perfil[campo] = valor_default

    return perfil


async def extrair_perfil(historico: list[dict]) -> dict:
    """
    Extrai o perfil biográfico rico da conversa usando Gemini 2.5 Flash.

    Usa response_mime_type="application/json" para garantir JSON válido.
    O modelo tem acesso a 1M tokens de contexto — ideal para históricos longos.

    Args:
        historico: Lista de mensagens {"role": str, "content": str}.

    Returns:
        Dict com o perfil biográfico completo (schema Epic 3.1).
        Em caso de falha, devolve _PERFIL_VAZIO sem lançar exceção.
    """
    if not historico:
        logger.warning("Gemini extrair_perfil | histórico vazio — a devolver perfil vazio.")
        return dict(_PERFIL_VAZIO)

    historico_texto = _historico_para_texto(historico)
    logger.info(
        "Gemini extrair_perfil | mensagens=%d | chars=%d",
        len(historico),
        len(historico_texto),
    )

    loop = asyncio.get_event_loop()
    try:
        perfil = await loop.run_in_executor(None, _extrair_perfil_sync, historico_texto)
        logger.info(
            "Gemini extrair_perfil | campos preenchidos: %s",
            [k for k, v in perfil.items() if v is not None and v != [] and v != {}],
        )
        return perfil

    except json.JSONDecodeError as exc:
        logger.error("Gemini | JSON inválido na extração: %s", exc)
        return dict(_PERFIL_VAZIO)

    except Exception as exc:
        logger.exception("Gemini | Erro na extração de perfil: %s", exc)
        return dict(_PERFIL_VAZIO)


# ---------------------------------------------------------------------------
# API pública — gerar_resumo_narrativo (Epic 3.3)
# ---------------------------------------------------------------------------

_PROMPT_RESUMO = """\
Com base na conversa abaixo entre um assistente e um idoso português, \
escreve um resumo narrativo de 1 a 2 parágrafos em Português de Portugal (PT-PT).

O resumo deve:
- Ser escrito na 3ª pessoa, com tom caloroso e respeitoso.
- Capturar os momentos e histórias mais marcantes partilhados.
- Usar linguagem fluida e literária (adequada para um livro de memórias).
- Não incluir informações que não foram mencionadas na conversa.
- Não usar emojis nem listas — apenas prosa corrida.

Responde APENAS com o texto do resumo, sem título nem introdução.

CONVERSA:
{conversa}
"""


def _gerar_resumo_sync(historico_texto: str) -> str:
    """Versão síncrona do gerador de resumo narrativo."""
    prompt = _PROMPT_RESUMO.format(conversa=historico_texto)
    config = genai_types.GenerateContentConfig(
        temperature=0.6,
        max_output_tokens=1024,
    )
    resposta = _generate_with_fallback(prompt, config)
    return resposta.text.strip()


def _resumo_groq_fallback(historico_texto: str) -> str:
    """Fallback: usa Groq (Llama 3) para gerar o resumo se o Gemini falhar (ex: 429)."""
    from app.services.groq_service import _get_client
    client = _get_client()
    
    mensagens = [
        {"role": "system", "content": "És um escritor exímio. Escreve um resumo narrativo de 1 a 2 parágrafos em PT-PT com base na conversa, na 3ª pessoa, num tom caloroso e literário. Não uses listas nem emojis."},
        {"role": "user", "content": f"CONVERSA:\n{historico_texto}"}
    ]
    
    resposta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.6,
        max_tokens=1024,
    )
    return resposta.choices[0].message.content.strip()


async def gerar_resumo_narrativo(historico: list[dict]) -> str:
    """
    Gera um resumo narrativo de 1-2 parágrafos da sessão em PT-PT.

    Adequado para o endpoint POST /sessao/encerrar (Epic 3.3) e para
    futura geração do livro de memórias (Epic 6.1).

    Args:
        historico: Lista de mensagens {"role": str, "content": str}.

    Returns:
        String com o resumo narrativo em PT-PT.
        Em caso de falha de ambos os modelos, devolve string vazia.
    """
    if not historico:
        return ""

    historico_texto = _historico_para_texto(historico)
    logger.info(
        "Gemini gerar_resumo_narrativo | mensagens=%d | chars=%d",
        len(historico),
        len(historico_texto),
    )

    loop = asyncio.get_event_loop()
    try:
        resumo = await loop.run_in_executor(None, _gerar_resumo_sync, historico_texto)
        logger.info("Gemini resumo gerado | chars=%d", len(resumo))
        return resumo
    except Exception as exc:
        logger.warning("Gemini falhou a gerar resumo (%s) — a usar Groq como fallback.", exc)
        try:
            resumo_groq = await loop.run_in_executor(None, _resumo_groq_fallback, historico_texto)
            logger.info("Groq resumo gerado (fallback) | chars=%d", len(resumo_groq))
            return resumo_groq
        except Exception as groq_exc:
            logger.exception("Groq fallback falhou ao gerar resumo: %s", groq_exc)
            return ""


# ---------------------------------------------------------------------------
# API pública — fundir_perfis (para langgraph_service)
# ---------------------------------------------------------------------------

_PROMPT_MERGE = """\
Funde os dois perfis biográficos abaixo num único perfil consolidado em JSON.

REGRAS:
- Preserva todos os factos de ambos os perfis.
- Em caso de conflito, prefere a informação mais recente (NOVOS FACTOS).
- Sem duplicados em listas.
- Mantém o schema exatamente igual ao fornecido.
- Responde APENAS com o JSON, sem texto adicional.

SCHEMA:
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
  "resumo_narrativo": null,
  "outros": {{}}
}}

PERFIL EXISTENTE:
{perfil_antigo}

NOVOS FACTOS:
{novos_factos}
"""


def _fundir_perfis_sync(perfil_antigo_str: str, novos_factos_str: str) -> dict:
    """Versão síncrona do merge de perfis via Gemini."""
    prompt = _PROMPT_MERGE.format(
        perfil_antigo=perfil_antigo_str,
        novos_factos=novos_factos_str,
    )
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
        max_output_tokens=2048,
    )

    resposta = _generate_with_fallback(prompt, config)
    raw = _clean_json_response(resposta.text)
    perfil = json.loads(raw)

    for campo, valor_default in _PERFIL_VAZIO.items():
        if campo not in perfil:
            perfil[campo] = valor_default

    return perfil


async def fundir_perfis(
    perfil_antigo: dict | None,
    novos_factos: dict | str,
) -> dict:
    """
    Funde o perfil existente com novos factos extraídos da sessão.

    Usado pelo langgraph_service como alternativa ao merge via Groq.
    Gemini é mais fiável para este tipo de tarefa estruturada com JSON.

    Args:
        perfil_antigo:  Perfil atual do PostgreSQL (pode ser None).
        novos_factos:   Dict ou string JSON com os novos factos da sessão.

    Returns:
        Dict com o perfil consolidado.
        Em caso de falha, devolve perfil_antigo intacto.
    """
    perfil_antigo_str = (
        json.dumps(perfil_antigo, ensure_ascii=False, indent=2)
        if perfil_antigo
        else "null (primeira sessão)"
    )

    novos_factos_str = (
        json.dumps(novos_factos, ensure_ascii=False, indent=2)
        if isinstance(novos_factos, dict)
        else str(novos_factos)
    )

    logger.info("Gemini fundir_perfis | iniciando merge...")

    loop = asyncio.get_event_loop()
    try:
        perfil_fundido = await loop.run_in_executor(
            None, _fundir_perfis_sync, perfil_antigo_str, novos_factos_str
        )
        logger.info("Gemini fundir_perfis | merge concluído com sucesso.")
        return perfil_fundido

    except json.JSONDecodeError as exc:
        logger.error("Gemini merge | JSON inválido: %s", exc)
        return perfil_antigo or dict(_PERFIL_VAZIO)

    except Exception as exc:
        logger.exception("Gemini merge | Erro: %s", exc)
        return perfil_antigo or dict(_PERFIL_VAZIO)
