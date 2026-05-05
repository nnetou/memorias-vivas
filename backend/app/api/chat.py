"""
Router de Chat — endpoints de conversação com o assistente Memórias Vivas.

Endpoints:
    POST /api/v1/chat/                               → resposta completa (JSON)
    POST /api/v1/chat/stream                         → resposta em streaming (SSE)
    POST /api/v1/chat/conversa                       → conversa por tema (JSON)
    POST /api/v1/chat/conversa/stream                → conversa por tema (SSE)
    POST /api/v1/chat/onboarding                     → fluxo de onboarding
    POST /api/v1/chat/conversa/personalizada         → conversa com perfil (JSON)
    POST /api/v1/chat/conversa/personalizada/stream  → conversa com perfil (SSE)
    POST /api/v1/chat/sessao/encerrar                → merge + persistência (Epic 4.2)

Memória curta  (Epic 4.1): Redis via session_id opcional.
Memória longa  (Epic 4.2): perfil do PostgreSQL injetado no Groq;
                           merge via LangGraph+Gemini ao encerrar sessão.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import groq_service, onboarding_service, profile_service
from app.services.langgraph_service import executar_merge
from app.services.redis_service import (
    get_historico,
    set_historico,
    append_interacao,
    delete_historico,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ===========================================================================
# Helpers de sessão (Epic 4.1)
# ===========================================================================

import uuid as _uuid_mod

async def _resolver_historico(
    session_id: str | None,
    historico_payload: list[dict] | None,
) -> tuple[list[dict], str]:
    """
    Resolve o histórico e garante que session_id existe sempre.

    - session_id presente → histórico vem do Redis
    - session_id ausente  → gera um novo UUID, inicia sessão Redis vazia
    """
    if not session_id:
        session_id = str(_uuid_mod.uuid4())
        logger.debug("Nova sessão criada: %s", session_id)
        # Se o cliente enviou histórico legado, persistimos já no Redis
        if historico_payload:
            await set_historico(session_id, historico_payload)
        return historico_payload or [], session_id

    historico = await get_historico(session_id)
    logger.debug("Histórico Redis | sessão=%s | msgs=%d", session_id, len(historico))
    return historico, session_id


async def _persistir_se_redis(
    session_id: str | None,
    user_msg: str,
    assistant_msg: str,
) -> None:
    if session_id:
        await append_interacao(session_id, user_msg, assistant_msg)


# ===========================================================================
# Schemas
# ===========================================================================

TEMAS_VALIDOS = ["memorias", "saude", "entretenimento", "familia", "exercicio", "geral"]

_SESSION_FIELD = Field(
    default=None,
    description="ID Redis da sessão. Se omitido, usa historico do payload.",
)


class MensagemEntrada(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=4096)
    historico: list[dict] | None = Field(default=None)
    session_id: str | None = _SESSION_FIELD


class MensagemInput(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=4096)
    tema: str = Field(default="geral")
    historico: list[dict] | None = Field(default=None)
    session_id: str | None = _SESSION_FIELD


class RespostaChat(BaseModel):
    resposta: str
    tema: str = Field(default="geral")
    ttft_ms: float
    session_id: str | None = Field(default=None)


class RespostaConversa(BaseModel):
    resposta: str
    tema: str
    ttft_ms: float
    session_id: str | None = Field(default=None)


class OnboardingInput(BaseModel):
    user_id: str
    mensagem: str = Field(default="", max_length=4096)
    historico: list[dict] = Field(default_factory=list)


class OnboardingResponse(BaseModel):
    pergunta: str | None
    onboarding_completo: bool
    perfil_extraido: dict | None = Field(default=None)
    historico_atualizado: list[dict]


class ConversaPersonalizadaInput(BaseModel):
    user_id: str
    mensagem: str = Field(..., min_length=1, max_length=4096)
    tema: str
    historico: list[dict] | None = Field(default=None)
    registar_tema: bool = Field(default=True)
    session_id: str | None = _SESSION_FIELD


class EncerrarSessaoInput(BaseModel):
    user_id: str = Field(..., description="UUID do utilizador.")
    session_id: str | None = Field(
        default=None,
        description="ID Redis a limpar após encerramento.",
    )
    historico_sessao: list[dict] = Field(
        ...,
        description="Histórico completo da sessão para extração Gemini.",
    )


class EncerrarSessaoResponse(BaseModel):
    user_id: str
    perfil_atualizado: bool
    mensagem: str
    erro: str | None = Field(default=None)


# ===========================================================================
# POST /  — chat genérico
# ===========================================================================

@router.post("/", response_model=RespostaChat)
async def chat_endpoint(payload: MensagemEntrada):
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)
    try:
        resultado = groq_service.chat(payload.mensagem, historico)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro Groq: {exc}")
    await _persistir_se_redis(session_id, payload.mensagem, resultado["resposta"])
    return {**resultado, "session_id": session_id}


# ===========================================================================
# POST /stream
# ===========================================================================

@router.post("/stream")
async def chat_stream_endpoint(payload: MensagemEntrada):
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)

    async def _gen() -> AsyncGenerator[str, None]:
        chunks: list[str] = []
        try:
            for chunk in groq_service.chat_stream(payload.mensagem, historico):
                chunks.append(chunk)
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERRO] {exc}\n\n"
            return
        finally:
            yield "data: [DONE]\n\n"
        await _persistir_se_redis(session_id, payload.mensagem, "".join(chunks))

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    if session_id:
        headers["X-Session-Id"] = session_id
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)


# ===========================================================================
# POST /conversa
# ===========================================================================

@router.post("/conversa", response_model=RespostaConversa)
async def conversa_endpoint(payload: MensagemInput):
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)
    try:
        resultado = groq_service.chat(
            mensagem=payload.mensagem,
            historico=historico,
            tema=payload.tema,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro Groq: {exc}")
    await _persistir_se_redis(session_id, payload.mensagem, resultado["resposta"])
    return {**resultado, "session_id": session_id}


@router.post("/conversa/stream")
async def conversa_stream_endpoint(payload: MensagemInput):
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)

    async def _gen() -> AsyncGenerator[str, None]:
        chunks: list[str] = []
        try:
            for chunk in groq_service.chat_stream(payload.mensagem, historico, payload.tema):
                chunks.append(chunk)
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERRO] {exc}\n\n"
            return
        finally:
            yield "data: [DONE]\n\n"
        await _persistir_se_redis(session_id, payload.mensagem, "".join(chunks))

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    if session_id:
        headers["X-Session-Id"] = session_id
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)


# ===========================================================================
# POST /onboarding  (INALTERADO)
# ===========================================================================

@router.post("/onboarding", response_model=OnboardingResponse)
async def onboarding_endpoint(
    payload: OnboardingInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Onboarding conversacional — o Groq conduz a conversa naturalmente.
    O frontend gere o historico_atualizado entre chamadas (stateless).

    Fluxo:
      1. Frontend chama com mensagem="" e historico=[] para iniciar.
      2. Backend pede ao Groq a primeira mensagem (boas-vindas + 1ª pergunta).
      3. Frontend envia resposta do utilizador → backend passa ao Groq.
      4. Groq gera próxima pergunta, validando a resposta anterior.
      5. Quando Groq decide que tem info suficiente, inclui [ONBOARDING_COMPLETO].
      6. Backend deteta a tag, extrai o perfil e persiste no PostgreSQL.
    """
    import asyncio

    historico = list(payload.historico)

    ja_feito = await profile_service.is_onboarding_done(payload.user_id, db)
    if ja_feito:
        raise HTTPException(
            status_code=409,
            detail="Onboarding já concluído. Use /conversa/personalizada.",
        )

    # Adicionar resposta do utilizador ao histórico
    if payload.mensagem.strip():
        historico.append({"role": "user", "content": payload.mensagem.strip()})

    # Gerar próxima mensagem do assistente via Groq
    loop = asyncio.get_event_loop()
    try:
        if not historico:
            # Primeira chamada — boas-vindas
            msg_assistente = await loop.run_in_executor(
                None, onboarding_service.get_boas_vindas
            )
        else:
            # Chamadas seguintes — próxima mensagem contextual
            hist_para_groq = historico
            msg_assistente = await loop.run_in_executor(
                None, lambda: onboarding_service.proxima_mensagem(hist_para_groq)
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro Groq: {exc}")

    # Verificar se o onboarding está completo
    if onboarding_service.is_onboarding_complete(msg_assistente):
        msg_limpa = onboarding_service.limpar_tag(msg_assistente)
        historico.append({"role": "assistant", "content": msg_limpa})

        # Extrair perfil e persistir
        try:
            perfil = await onboarding_service.extract_profile_with_gemini(historico)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Erro extração: {exc}")

        nome = (perfil or {}).get("nome")
        await profile_service.save_profile(
            user_id=payload.user_id,
            perfil_json=perfil,
            historico_onboarding=historico,
            db=db,
        )
        await profile_service.mark_onboarding_done(
            user_id=payload.user_id,
            nome=nome,
            db=db,
        )
        return OnboardingResponse(
            pergunta=msg_limpa,
            onboarding_completo=True,
            perfil_extraido=perfil,
            historico_atualizado=historico,
        )

    # Adicionar mensagem ao histórico e devolver
    historico.append({"role": "assistant", "content": msg_assistente})
    return OnboardingResponse(
        pergunta=msg_assistente,
        onboarding_completo=False,
        historico_atualizado=historico,
    )


# ===========================================================================
# POST /conversa/personalizada  (Epic 4.2 — perfil do PostgreSQL injetado)
# ===========================================================================

@router.post("/conversa/personalizada", response_model=RespostaConversa)
async def conversa_personalizada_endpoint(
    payload: ConversaPersonalizadaInput,
    db: AsyncSession = Depends(get_db),
):
    """
    O perfil biográfico é carregado do PostgreSQL e passado ao groq_service,
    que já o injeta no system prompt via _build_dynamic_system_prompt.
    Sem hacks adicionais — o groq_service faz o trabalho correto.
    """
    # ── Diagnóstico: confirmar que o user_id chega bem formado ───────────────
    import uuid as _uuid
    try:
        _uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"user_id inválido: '{payload.user_id}' não é um UUID válido.")
    # ────────────────────────────────────────────────────────────────────────

    perfil_db = await profile_service.get_profile(payload.user_id, db)

    # ── Diagnóstico: confirmar se o perfil foi encontrado e qual o conteúdo ──
    if perfil_db is None:
        logger.warning(
            "DIAGNÓSTICO | user=%s | perfil NÃO encontrado na DB "
            "(verifica se o utilizador_id na tabela corresponde exactamente a este UUID)",
            payload.user_id,
        )
        raise HTTPException(
            status_code=404,
            detail="Perfil não encontrado. Complete o onboarding primeiro.",
        )

    logger.info(
        "DIAGNÓSTICO | user=%s | perfil encontrado | conteúdo: %s",
        payload.user_id,
        perfil_db.perfil_json,
    )
    # ────────────────────────────────────────────────────────────────────────

    temas_anteriores = await profile_service.get_temas_explorados(payload.user_id, db)
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)

    try:
        resultado = groq_service.conversa_personalizada(
            mensagem=payload.mensagem,
            tema=payload.tema,
            perfil_json=perfil_db.perfil_json,   # perfil do PostgreSQL, direto
            temas_anteriores=temas_anteriores,
            historico=historico,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro Groq: {exc}")

    if payload.registar_tema:
        await profile_service.add_tema_explorado(payload.user_id, payload.tema, db)

    await _persistir_se_redis(session_id, payload.mensagem, resultado["resposta"])
    return {**resultado, "session_id": session_id}


@router.post("/conversa/personalizada/stream")
async def conversa_personalizada_stream_endpoint(
    payload: ConversaPersonalizadaInput,
    db: AsyncSession = Depends(get_db),
):
    perfil_db = await profile_service.get_profile(payload.user_id, db)
    if perfil_db is None:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")

    temas_anteriores = await profile_service.get_temas_explorados(payload.user_id, db)
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)

    if payload.registar_tema:
        await profile_service.add_tema_explorado(payload.user_id, payload.tema, db)

    async def _gen() -> AsyncGenerator[str, None]:
        chunks: list[str] = []
        try:
            for chunk in groq_service.conversa_personalizada_stream(
                mensagem=payload.mensagem,
                tema=payload.tema,
                perfil_json=perfil_db.perfil_json,
                temas_anteriores=temas_anteriores,
                historico=historico,
            ):
                chunks.append(chunk)
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERRO] {exc}\n\n"
            return
        finally:
            yield "data: [DONE]\n\n"
        await _persistir_se_redis(session_id, payload.mensagem, "".join(chunks))

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    if session_id:
        headers["X-Session-Id"] = session_id
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)


# ===========================================================================
# POST /sessao/encerrar  (Epic 4.2 — merge e persistência)
# ===========================================================================

@router.post("/sessao/encerrar", response_model=EncerrarSessaoResponse)
async def encerrar_sessao(
    payload: EncerrarSessaoInput,
    db: AsyncSession = Depends(get_db),
):
    """
    Encerra a sessão e atualiza a memória longa do idoso.

    Fluxo:
        1. Gemini extrai novos factos do historico_sessao.
        2. LangGraph faz merge: perfil_antigo (PostgreSQL) + novos_factos.
        3. Persiste o perfil consolidado no PostgreSQL.
        4. Limpa o histórico Redis (se session_id fornecido).

    O frontend deve sempre enviar historico_sessao completo — mesmo quando
    usa Redis — pois o Redis pode ter expirado.
    """
    erro: str | None = None

    # 1. Gemini extrai novos factos da sessão
    try:
        novos_factos = await onboarding_service.extract_profile_with_gemini(
            payload.historico_sessao
        )
        resumo_sessao_str = json.dumps(novos_factos or {}, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Extração Gemini falhou para user=%s: %s", payload.user_id, exc)
        # Fallback: usa o histórico como texto simples
        resumo_sessao_str = "\n".join(
            f"{m.get('role','?').upper()}: {m.get('content','')}"
            for m in payload.historico_sessao
            if isinstance(m, dict)
        )
        erro = f"Extração Gemini: {exc}"

    # 2. Carrega perfil atual e executa merge via LangGraph
    perfil_db = await profile_service.get_profile(payload.user_id, db)
    perfil_antigo = perfil_db.perfil_json if perfil_db else None

    try:
        perfil_fundido = await executar_merge(
            user_id=payload.user_id,
            perfil_antigo=perfil_antigo,
            resumo_sessao=resumo_sessao_str,
        )
    except Exception as exc:
        logger.exception("Merge falhou para user=%s", payload.user_id)
        perfil_fundido = perfil_antigo or {}
        erro = (erro or "") + f" | Merge: {exc}"

    # 3. Persiste no PostgreSQL
    perfil_atualizado = False
    if perfil_fundido:
        try:
            await profile_service.save_profile(
                user_id=payload.user_id,
                perfil_json=perfil_fundido,
                historico_onboarding=payload.historico_sessao,
                db=db,
            )
            await db.commit()   # garante persistência no PostgreSQL antes de limpar o Redis
            perfil_atualizado = True
            logger.info("Perfil atualizado | user=%s", payload.user_id)
        except Exception as exc:
            logger.exception("Erro ao guardar perfil | user=%s", payload.user_id)
            erro = (erro or "") + f" | Save: {exc}"

    # 4. Limpa Redis
    if payload.session_id:
        await delete_historico(payload.session_id)

    return EncerrarSessaoResponse(
        user_id=payload.user_id,
        perfil_atualizado=perfil_atualizado,
        mensagem="Sessão encerrada e perfil atualizado." if perfil_atualizado else "Sessão encerrada com erros.",
        erro=erro,
    )