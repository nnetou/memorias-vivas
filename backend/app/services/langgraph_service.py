"""
app/services/langgraph_service.py — Memória Longa (Epic 4.2).

Responsabilidade única:
    Dado um perfil_antigo (PostgreSQL) e um resumo_sessao (Gemini),
    produz um perfil_fundido consolidado usando o Gemini 2.5 Flash como
    "motor de merge" inteligente.

Schema do perfil (alinhado com onboarding_service):
    {
        "nome":             str | null,
        "terra_natal":      str | null,
        "familia":          str | null,
        "profissao":        str | null,
        "memoria_marcante": str | null,
        "outros":           dict
    }

Checkpointer:
    MemorySaver — in-memory, scoped ao processo.
    A fonte da verdade é sempre o PostgreSQL (profile_service).
    O LangGraph gere apenas a lógica de estado do merge.

API pública:
    executar_merge(user_id, perfil_antigo, resumo_sessao) → dict
"""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Any, TypedDict

from groq import Groq
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings

logger = logging.getLogger(__name__)

_groq_client: Groq | None = None

def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


# ---------------------------------------------------------------------------
# Estado do Grafo
# ---------------------------------------------------------------------------

class EstadoMerge(TypedDict):
    """
    Estado partilhado entre os nós do grafo.

    perfil_antigo:  Perfil atual do PostgreSQL. None na primeira sessão.
    resumo_sessao:  JSON string extraído pelo Gemini no fim da sessão.
    perfil_fundido: Resultado do merge. Preenchido pelo nó merge_perfil.
    erro:           Mensagem de erro se o nó falhar.
    """
    perfil_antigo: dict | None
    resumo_sessao: str
    perfil_fundido: dict | None
    erro: str | None


# ---------------------------------------------------------------------------
# Prompt de merge — schema alinhado com onboarding_service
# ---------------------------------------------------------------------------

_MERGE_PROMPT = """\
Funde os dois perfis biográficos em JSON. Sem duplicados. Preserva todos os factos. PT-PT.
Certifica-te de que o array "linha_temporal" contendo objetos com {"periodo": "...", "acontecimento": "..."} é fundido corretamente, unindo e ordenando cronologicamente os eventos sempre que possível.

PERFIL EXISTENTE: {perfil_antigo}
NOVOS FACTOS: {resumo_sessao}

Responde APENAS com JSON, sem texto extra:
{{"nome":null,"terra_natal":null,"familia":null,"profissao":null,"memoria_marcante":null,"pessoas":[],"locais":[],"datas_aproximadas":[],"eventos_marcantes":[],"tradicoes":[],"expressoes_regionais":[],"momentos_chave":[],"linha_temporal":[],"resumo_narrativo":null,"outros":{{}}}}
"""


# ---------------------------------------------------------------------------
# Nó de Merge — Gemini 2.5 Flash (com fallback para Groq)
# ---------------------------------------------------------------------------

def _merge_perfil(estado: EstadoMerge) -> dict[str, Any]:
    """
    Nó LangGraph: chama o Gemini 2.5 Flash para fundir os dois perfis.
    Em caso de falha do Gemini, faz fallback para Groq.
    Em caso de falha total, devolve o perfil_antigo intacto.
    """
    perfil_antigo = estado.get("perfil_antigo")
    resumo_sessao = estado.get("resumo_sessao", "")

    # ── Tentativa 1: Gemini 2.5 Flash ────────────────────────────────────────
    try:
        from app.services.gemini_service import _fundir_perfis_sync

        perfil_antigo_str = (
            json.dumps(perfil_antigo, ensure_ascii=False, indent=2)
            if perfil_antigo
            else "null (primeira sessão)"
        )

        perfil_fundido = _fundir_perfis_sync(perfil_antigo_str, resumo_sessao)
        logger.info("Merge concluído via Gemini 2.5 Flash.")
        return {"perfil_fundido": perfil_fundido, "erro": None}

    except Exception as exc_gemini:
        logger.warning("Merge Gemini falhou (%s) — a usar Groq como fallback.", exc_gemini)

    # ── Tentativa 2: Groq (Llama 3.3 70B) ────────────────────────────────────
    try:
        perfil_antigo_str = (
            json.dumps(perfil_antigo, ensure_ascii=False, indent=2)
            if perfil_antigo
            else "null"
        )

        prompt = _MERGE_PROMPT.format(
            perfil_antigo=perfil_antigo_str,
            resumo_sessao=resumo_sessao,
        )

        resposta = _get_groq().chat.completions.create(
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
        )
        raw = resposta.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        perfil_fundido = json.loads(raw.strip())

        if "outros" not in perfil_fundido:
            perfil_fundido["outros"] = {}

        logger.info("Merge concluído via Groq (fallback).")
        return {"perfil_fundido": perfil_fundido, "erro": None}

    except Exception as exc_groq:
        logger.exception("Merge Groq (fallback) também falhou: %s", exc_groq)
        return {
            "perfil_fundido": perfil_antigo,
            "erro": str(exc_groq),
        }



# ---------------------------------------------------------------------------
# Construção do Grafo (singleton)
# ---------------------------------------------------------------------------

_checkpointer = MemorySaver()


def _build_graph() -> Any:
    grafo = StateGraph(EstadoMerge)
    grafo.add_node("merge_perfil", _merge_perfil)
    grafo.set_entry_point("merge_perfil")
    grafo.add_edge("merge_perfil", END)
    return grafo.compile(checkpointer=_checkpointer)


_grafo = _build_graph()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

async def executar_merge(
    user_id: str,
    perfil_antigo: dict | None,
    resumo_sessao: str,
) -> dict:
    """
    Executa o grafo de merge e devolve o perfil biográfico consolidado.

    O Gemini SDK é síncrono — corremos num executor para não bloquear
    o event loop do FastAPI.

    Args:
        user_id:       ID do utilizador (thread_id do LangGraph).
        perfil_antigo: Perfil atual do PostgreSQL (pode ser None).
        resumo_sessao: JSON string extraído pelo Gemini no fim da sessão.

    Returns:
        Dict com o perfil consolidado (schema onboarding_service).
        Em caso de erro, devolve perfil_antigo intacto (nunca lança exceção).
    """
    config = {"configurable": {"thread_id": user_id}}
    estado_inicial: EstadoMerge = {
        "perfil_antigo": perfil_antigo,
        "resumo_sessao": resumo_sessao,
        "perfil_fundido": None,
        "erro": None,
    }

    loop = asyncio.get_event_loop()
    resultado = await loop.run_in_executor(
        None,
        lambda: _grafo.invoke(estado_inicial, config=config),
    )

    if resultado.get("erro"):
        logger.warning(
            "Merge com fallback para user=%s | erro: %s",
            user_id, resultado["erro"],
        )

    return resultado.get("perfil_fundido") or perfil_antigo or {}