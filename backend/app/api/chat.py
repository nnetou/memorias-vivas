"""
Router de Chat — endpoints de conversação com o assistente Memórias Vivas.

Endpoints:
    POST /api/v1/chat/                       → resposta completa (JSON)
    POST /api/v1/chat/stream                 → resposta em streaming (SSE)
    POST /api/v1/chat/conversa               → conversa genérica por tema (JSON)
    POST /api/v1/chat/conversa/stream        → conversa genérica por tema (SSE)

    POST /api/v1/chat/onboarding             → fluxo de onboarding (1.º acesso)
    POST /api/v1/chat/conversa/personalizada         → conversa dinâmica pós-onboarding (JSON)
    POST /api/v1/chat/conversa/personalizada/stream  → idem, em streaming (SSE)
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import groq_service
from app.services import onboarding_service, profile_service
from app.services.redis_service import (
    get_historico,
    append_interacao,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ===========================================================================
# Helpers de sessão
# ===========================================================================
 
async def _resolver_historico(
    session_id: str | None,
    historico_payload: list[dict] | None,
) -> tuple[list[dict], str | None]:

    if session_id:
        historico = await get_historico(session_id)
        logger.debug("Histórico Redis | sessão=%s | msgs=%d", session_id, len(historico))
        return historico, session_id
 
    return historico_payload or [], None
 
 
async def _persistir_se_redis(
    session_id: str | None,
    user_msg: str,
    assistant_msg: str,
) -> None:
    if session_id:
        await append_interacao(session_id, user_msg, assistant_msg)

# ===========================================================================
# Schemas comuns
# ===========================================================================

TEMAS_VALIDOS = ["memorias", "saude", "entretenimento", "familia", "exercicio", "geral"]

_SESSION_ID_FIELD = Field(
    default=None,
    description=(
        "ID de sessão para gestão de histórico via Redis. "
        "Se omitido, o histórico deve ser enviado em cada pedido (modo legado)."
    ),
)

class MensagemEntrada(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=4096)
    historico: list[dict] | None = Field(
        default=None,
        description="Histórico opcional [{role, content}, ...]. Ignorado se session_id for fornecido."
    )
    session_id: str | None = _SESSION_ID_FIELD


class MensagemInput(BaseModel):
    """Schema para conversa genérica por tema."""
    mensagem: str = Field(..., min_length=1, max_length=4096)
    tema: str = Field(default="geral", description=f"Tema válido: {TEMAS_VALIDOS}")
    historico: list[dict] |  None = Field(
        default=None,
        description="Ignorado se session_id for fornecido."
    )
    session_id: str | None = _SESSION_ID_FIELD


class RespostaChat(BaseModel):
    resposta: str
    tema: str = Field(default="geral")
    ttft_ms: float = Field(description="Tempo até ao primeiro token (ms).")
    session_id: str | None = Field(
        default=None,
        description="session_id activo, se Redis foi usado. None caso contrário.",
    )


class RespostaConversa(BaseModel):
    resposta: str
    tema: str
    ttft_ms: float
    session_id: str | None = Field(default=None)


# ===========================================================================
# Schemas de Onboarding
# ===========================================================================

class OnboardingInput(BaseModel):
    """
    Payload enviado em cada turno do onboarding.

    - Na 1.ª chamada, `mensagem` pode ser vazia (ou "começar") para receber as boas-vindas.
    - Nas seguintes, `mensagem` contém a resposta do idoso à pergunta anterior.
    """
    user_id: str = Field(..., description="UUID único do utilizador.")
    mensagem: str = Field(default="", max_length=4096, description="Resposta do utilizador.")
    historico: list[dict] = Field(
        default_factory=list,
        description="Histórico acumulado da sessão de onboarding [{role, content}]."
    )


class OnboardingResponse(BaseModel):
    pergunta: str | None = Field(
        description="Próxima pergunta de onboarding. None quando o onboarding está completo."
    )
    onboarding_completo: bool
    perfil_extraido: dict | None = Field(
        default=None,
        description="Perfil biográfico JSON extraído pelo Gemini (só presente quando completo)."
    )
    historico_atualizado: list[dict] = Field(
        description="Histórico actualizado para o frontend guardar e reenviar."
    )


# ===========================================================================
# Schemas de Conversa Personalizada (pós-onboarding)
# ===========================================================================

class ConversaPersonalizadaInput(BaseModel):
    """Payload para a conversa dinâmica pós-onboarding."""
    user_id: str = Field(..., description="UUID único do utilizador.")
    mensagem: str = Field(..., min_length=1, max_length=4096)
    tema: str = Field(..., description="Tema da conversa (ex: infancia, trabalho, receitas).")
    historico: list[dict] | None = Field(
        default=None,
        description="Histórico da sessão actual."
    )
    registar_tema: bool = Field(
        default=True,
        description="Se True, adiciona o tema à lista de temas explorados do utilizador."
    )
    session_id: str | None = _SESSION_ID_FIELD


# ===========================================================================
# POST /api/v1/chat/  — resposta completa genérica
# ===========================================================================

@router.post("/", response_model=RespostaChat, summary="Enviar mensagem ao assistente")
async def chat_endpoint(payload: MensagemEntrada):
    """Envia uma mensagem ao Llama 3.3 70B e devolve a resposta completa em PT-PT."""
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)
 
    try:
        resultado = groq_service.chat(payload.mensagem, historico)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na API Groq: {exc}")
 
    await _persistir_se_redis(session_id, payload.mensagem, resultado["resposta"])
    return {**resultado, "session_id": session_id}


# ===========================================================================
# POST /api/v1/chat/stream  — streaming genérico
# ===========================================================================

@router.post("/stream", summary="Chat em streaming (SSE)")
async def chat_stream_endpoint(payload: MensagemEntrada):
    """Versão streaming do chat — devolve chunks via Server-Sent Events."""
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
# POST /api/v1/chat/conversa  — conversa genérica por tema
# ===========================================================================

@router.post("/conversa", response_model=RespostaConversa, summary="Conversa genérica por tema")
async def conversa_endpoint(payload: MensagemInput):
    """Conversa com system prompt adaptado ao tema (sem perfil biográfico)."""
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
        raise HTTPException(status_code=502, detail=f"Erro na API Groq: {exc}")
 
    await _persistir_se_redis(session_id, payload.mensagem, resultado["resposta"])
    return {**resultado, "session_id": session_id}


@router.post("/conversa/stream", summary="Conversa genérica por tema em streaming (SSE)")
async def conversa_stream_endpoint(payload: MensagemInput):
    """Versão streaming da conversa por tema."""
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
# POST /api/v1/chat/onboarding  — fluxo de onboarding (1.º acesso)
# ===========================================================================

@router.post(
    "/onboarding",
    response_model=OnboardingResponse,
    summary="Onboarding — recolha de perfil biográfico (1.º acesso)",
)
async def onboarding_endpoint(
    payload: OnboardingInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Conduz a conversa de onboarding com 5 perguntas fixas.

    **Fluxo:**
    1. Frontend chama este endpoint com `historico=[]` e `mensagem=""` para começar.
    2. Endpoint devolve a mensagem de boas-vindas + 1.ª pergunta.
    3. Frontend guarda o `historico_atualizado` e reenvia com a resposta do utilizador.
    4. Repete até `onboarding_completo=true`.
    5. Quando completo, o Gemini extrai o perfil e persiste no PostgreSQL.
    """
    historico = list(payload.historico)

    # Verifica se o utilizador já completou o onboarding
    ja_feito = await profile_service.is_onboarding_done(payload.user_id, db)
    if ja_feito:
        raise HTTPException(
            status_code=409,
            detail="Onboarding já concluído para este utilizador. Use /conversa/personalizada."
        )

    # Acrescenta a resposta do utilizador ao histórico (se não estiver vazia)
    if payload.mensagem.strip():
        historico.append({"role": "user", "content": payload.mensagem.strip()})

    # Verifica se o onboarding está completo
    if onboarding_service.is_onboarding_complete(historico):
        # Extrai perfil com Gemini (operação assíncrona)
        try:
            perfil = await onboarding_service.extract_profile_with_gemini(historico)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Erro ao extrair perfil com Gemini: {exc}"
            )

        # Persiste no PostgreSQL
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
            pergunta=None,
            onboarding_completo=True,
            perfil_extraido=perfil,
            historico_atualizado=historico,
        )

    # Determina a próxima pergunta
    proxima_pergunta = onboarding_service.get_next_question(historico)

    if proxima_pergunta is None:
        # Caso de segurança: todas as perguntas feitas mas sem resposta final
        return OnboardingResponse(
            pergunta=None,
            onboarding_completo=False,
            historico_atualizado=historico,
        )

    # Primeira vez: adiciona boas-vindas antes da 1.ª pergunta
    if not historico:
        boas_vindas = onboarding_service.get_boas_vindas()
        historico.append({"role": "assistant", "content": boas_vindas})

    # Acrescenta a pergunta ao histórico
    historico.append({"role": "assistant", "content": proxima_pergunta})

    return OnboardingResponse(
        pergunta=proxima_pergunta,
        onboarding_completo=False,
        historico_atualizado=historico,
    )


# ===========================================================================
# POST /api/v1/chat/conversa/personalizada  — dinâmica pós-onboarding
# ===========================================================================

@router.post(
    "/conversa/personalizada",
    response_model=RespostaConversa,
    summary="Conversa personalizada com base no perfil do idoso",
)
async def conversa_personalizada_endpoint(
    payload: ConversaPersonalizadaInput,
    db: AsyncSession = Depends(get_db),
):
    """Gera a próxima pergunta personalizada. Requer onboarding concluído."""
    perfil_db = await profile_service.get_profile(payload.user_id, db)
    if perfil_db is None:
        raise HTTPException(
            status_code=404,
            detail="Perfil não encontrado. Complete o onboarding primeiro."
        )
 
    temas_anteriores = await profile_service.get_temas_explorados(payload.user_id, db)
    historico, session_id = await _resolver_historico(payload.session_id, payload.historico)
 
    try:
        resultado = groq_service.conversa_personalizada(
            mensagem=payload.mensagem,
            tema=payload.tema,
            perfil_json=perfil_db.perfil_json,
            temas_anteriores=temas_anteriores,
            historico=historico,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na API Groq: {exc}")
 
    if payload.registar_tema:
        await profile_service.add_tema_explorado(payload.user_id, payload.tema, db)
 
    await _persistir_se_redis(session_id, payload.mensagem, resultado["resposta"])
    return {**resultado, "session_id": session_id}

@router.post(
    "/conversa/personalizada/stream",
    summary="Conversa personalizada em streaming (SSE)",
)
async def conversa_personalizada_stream_endpoint(
    payload: ConversaPersonalizadaInput,
    db: AsyncSession = Depends(get_db),
):
    """Versão streaming da conversa personalizada."""
    perfil_db = await profile_service.get_profile(payload.user_id, db)
    if perfil_db is None:
        raise HTTPException(
            status_code=404,
            detail="Perfil não encontrado. Complete o onboarding primeiro."
        )
 
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