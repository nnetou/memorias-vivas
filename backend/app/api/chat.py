"""
Router de Chat — expõe os endpoints de conversação com o modelo Groq.

Endpoints:
    POST /api/v1/chat              → resposta completa (JSON)
    POST /api/v1/chat/stream       → resposta em streaming (SSE)
    POST /api/v1/chat/conversa     → conversa guiada por tema (JSON)
    POST /api/v1/chat/conversa/stream → conversa guiada por tema (SSE)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.services import groq_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas de entrada / saída
# ---------------------------------------------------------------------------
class MensagemEntrada(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=4096,
                          description="Texto do utilizador.")
    historico: list[dict] | None = Field(
        default=None,
        description="Histórico opcional de mensagens anteriores [{'role': ..., 'content': ...}]."
    )


TEMAS_VALIDOS = ["memorias", "saude", "entretenimento", "familia", "exercicio", "geral"]


class MensagemInput(BaseModel):
    """Schema para conversa guiada por tema."""
    mensagem: str = Field(..., min_length=1, max_length=4096,
                          description="Texto do utilizador.")
    tema: str = Field(
        default="geral",
        description=f"Tema da conversa. Valores válidos: {TEMAS_VALIDOS}"
    )
    historico: list[dict] | None = Field(
        default=None,
        description="Histórico opcional de mensagens anteriores."
    )


class EntrevistaInput(BaseModel):
    """Schema para entrevista estruturada pelo guioes.py."""
    mensagem: str = Field(..., min_length=1, max_length=4096,
                          description="Texto do utilizador.")
    tema: str = Field(
        ...,
        description="Chave do tema do guião (ex: infancia, trabalho)."
    )
    historico: list[dict] | None = Field(
        default=None,
        description="Histórico opcional de mensagens anteriores."
    )
    perguntas_feitas: list[str] | None = Field(
        default=None,
        description="Lista de perguntas já feitas pelo assistente nesta sessão."
    )


class RespostaConversa(BaseModel):
    resposta: str
    tema: str = Field(description="Tema usado na conversa.")
    ttft_ms: float = Field(description="Tempo até ao primeiro token, em ms.")


class RespostaChat(BaseModel):
    resposta: str
    tema: str = Field(default="geral")
    ttft_ms: float = Field(description="Tempo até ao primeiro token, em milissegundos.")


# ---------------------------------------------------------------------------
# POST /api/v1/chat  — resposta completa
# ---------------------------------------------------------------------------
@router.post("/", response_model=RespostaChat, summary="Enviar mensagem ao assistente")
async def chat_endpoint(payload: MensagemEntrada):
    """
    Envia uma mensagem ao modelo Llama 3.3 70B (via Groq) e devolve
    a resposta completa em PT-PT.
    """
    try:
        resultado = groq_service.chat(payload.mensagem, payload.historico)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na API Groq: {exc}")

    return resultado


# ---------------------------------------------------------------------------
# POST /api/v1/chat/stream  — Server-Sent Events
# ---------------------------------------------------------------------------
@router.post("/stream", summary="Chat em streaming (SSE)")
async def chat_stream_endpoint(payload: MensagemEntrada):
    """
    Versão streaming do chat — devolve os chunks de texto à medida que
    o modelo os gera (ideal para UIs com resposta progressiva).
    """
    def _generator():
        try:
            for chunk in groq_service.chat_stream(payload.mensagem, payload.historico):
                # Formato SSE: "data: <texto>\n\n"
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERRO] {exc}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# POST /api/v1/chat/conversa  — conversa guiada por tema (completa)
# ---------------------------------------------------------------------------
@router.post("/conversa", response_model=RespostaConversa, summary="Conversa guiada por tema")
async def conversa_endpoint(payload: MensagemInput):
    """
    Envia uma mensagem ao assistente com um tema específico.
    O modelé adapta o system prompt conforme o tema escolhido.

    **Temas disponíveis:** `memorias`, `saude`, `entretenimento`, `familia`, `exercicio`, `geral`
    """
    try:
        resultado = groq_service.chat(
            mensagem=payload.mensagem,
            historico=payload.historico,
            tema=payload.tema,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na API Groq: {exc}")

    return resultado


# ---------------------------------------------------------------------------
# POST /api/v1/chat/conversa/stream  — conversa guiada por tema (SSE)
# ---------------------------------------------------------------------------
@router.post("/conversa/stream", summary="Conversa guiada por tema em streaming (SSE)")
async def conversa_stream_endpoint(payload: MensagemInput):
    """
    Versão streaming da conversa guiada por tema.
    Ideal para UIs com resposta progressiva em tempo real.
    """
    def _generator():
        try:
            for chunk in groq_service.chat_stream(
                payload.mensagem, payload.historico, payload.tema
            ):
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERRO] {exc}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ===========================================================================
# ENDPOINTS DE ENTREVISTA (Guiões)
# ===========================================================================

@router.post("/entrevista", response_model=RespostaConversa, summary="Entrevista estruturada por guião")
async def entrevista_endpoint(payload: EntrevistaInput):
    """
    Usa os guiões definidos em `app.services.guioes.py`.
    O assistente não repete perguntas que venham na lista `perguntas_feitas`.
    """
    try:
        resultado = groq_service.entrevista_chat(
            mensagem=payload.mensagem,
            tema=payload.tema,
            perguntas_feitas=payload.perguntas_feitas,
            historico=payload.historico,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na API Groq: {exc}")

    return resultado


@router.post("/entrevista/stream", summary="Entrevista estruturada em streaming")
async def entrevista_stream_endpoint(payload: EntrevistaInput):
    """
    Versão streaming da entrevista.
    """
    def _generator():
        try:
            for chunk in groq_service.entrevista_chat_stream(
                mensagem=payload.mensagem,
                tema=payload.tema,
                perguntas_feitas=payload.perguntas_feitas,
                historico=payload.historico
            ):
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERRO] {exc}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
