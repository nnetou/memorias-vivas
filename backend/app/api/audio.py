"""
app/api/audio.py — Endpoints de voz para o projeto Memórias Vivas.

Endpoints:
    POST /api/v1/audio/transcrever   → STT: áudio → texto (Whisper Large V3) [Epic 5.1]
    POST /api/v1/audio/sintetizar    → TTS: texto → áudio MP3 (edge-tts Neural) [Epic 5.2]
    GET  /api/v1/audio/vozes         → lista de vozes PT-PT disponíveis
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.services.whisper_service import (
    EXTENSOES_SUPORTADAS,
    FORMATOS_SUPORTADOS,
    MAX_AUDIO_BYTES,
    transcrever,
)
from app.services.tts_service import (
    VOZ_PADRAO,
    VOZES_DISPONIVEIS,
    sintetizar,
    sintetizar_streaming,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TranscricaoResponse(BaseModel):
    texto: str
    duracao_ms: float
    modelo: str
    idioma: str
    tamanho_bytes: int


class SintetizarInput(BaseModel):
    texto: str
    voz: str = VOZ_PADRAO
    streaming: bool = False


class VozInfo(BaseModel):
    id: str
    nome_completo: str
    genero: str


# ---------------------------------------------------------------------------
# POST /transcrever  (Epic 5.1)
# ---------------------------------------------------------------------------

@router.post(
    "/transcrever",
    response_model=TranscricaoResponse,
    summary="STT — Transcrever áudio para texto (Whisper Large V3)",
)
async def transcrever_audio(
    audio: UploadFile = File(
        ...,
        description="Ficheiro de áudio. Formatos: mp3, wav, webm, ogg, flac, m4a, mp4.",
    ),
    prompt_hint: str | None = Form(
        default=None,
        description="Contexto opcional para melhorar precisão (ex: nome do utilizador, tema).",
    ),
):
    """
    Transcreve áudio para texto em PT-PT usando Whisper Large V3 da Groq.

    **Testar no Postman:**
    - Body → form-data
    - `audio` (File): ficheiro de áudio
    - `prompt_hint` (Text, opcional): ex. "Manuel Silva, Évora, carpinteiro"
    """
    filename = audio.filename or "audio.webm"
    extensao = os.path.splitext(filename)[1].lower()
    content_type = (audio.content_type or "").lower()

    formato_valido = (
        content_type in FORMATOS_SUPORTADOS
        or extensao in EXTENSOES_SUPORTADAS
        or content_type == "application/octet-stream"
    )
    if not formato_valido:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Formato não suportado: '{content_type}' / '{extensao}'. "
                f"Formatos aceites: {', '.join(sorted(EXTENSOES_SUPORTADAS))}"
            ),
        )

    audio_bytes = await audio.read()

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Ficheiro demasiado grande: {len(audio_bytes)/1024/1024:.1f} MB (máximo: 25 MB).",
        )
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Ficheiro de áudio vazio.")

    try:
        resultado = transcrever(
            audio_bytes=audio_bytes,
            filename=filename,
            prompt_hint=prompt_hint,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return TranscricaoResponse(
        texto=resultado.texto,
        duracao_ms=resultado.duracao_ms,
        modelo=resultado.modelo,
        idioma=resultado.idioma,
        tamanho_bytes=len(audio_bytes),
    )


# ---------------------------------------------------------------------------
# POST /sintetizar  (Epic 5.2)
# ---------------------------------------------------------------------------

@router.post(
    "/sintetizar",
    summary="TTS — Sintetizar texto para áudio MP3 (edge-tts Neural PT-PT)",
    responses={
        200: {
            "content": {"audio/mpeg": {}},
            "description": "Ficheiro MP3 com a voz sintetizada.",
        }
    },
)
async def sintetizar_texto(payload: SintetizarInput):
    """
    Converte texto em áudio MP3 em PT-PT usando vozes neurais (edge-tts).

    - Voz padrão: `pt-PT-RaquelNeural` (feminina, clara)
    - Voz alternativa: `pt-PT-DuarteNeural` (masculina, pausada)
    - `streaming: true` → devolve áudio em chunks (menor latência percebida)
    - `streaming: false` → devolve MP3 completo de uma vez

    **Testar no Postman:**
    - Body → raw JSON
    - Resultado: ficheiro MP3 — clicar em "Send and Download"
    """
    if not payload.texto.strip():
        raise HTTPException(status_code=400, detail="Texto vazio.")

    if len(payload.texto) > 5000:
        raise HTTPException(
            status_code=400,
            detail=f"Texto demasiado longo: {len(payload.texto)} caracteres (máximo: 5000).",
        )

    logger.info(
        "TTS request | voz=%s | chars=%d | streaming=%s",
        payload.voz, len(payload.texto), payload.streaming,
    )

    headers = {
        "Content-Disposition": 'attachment; filename="resposta.mp3"',
        "X-Voz": payload.voz,
    }

    if payload.streaming:
        # Streaming — envia chunks à medida que são gerados
        async def _audio_stream():
            try:
                async for chunk in sintetizar_streaming(payload.texto, payload.voz):
                    yield chunk
            except RuntimeError as exc:
                logger.error("Erro TTS streaming: %s", exc)

        return StreamingResponse(
            _audio_stream(),
            media_type="audio/mpeg",
            headers=headers,
        )

    # Resposta completa
    try:
        audio_bytes = await sintetizar(payload.texto, payload.voz)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={**headers, "Content-Length": str(len(audio_bytes))},
    )


# ---------------------------------------------------------------------------
# GET /vozes
# ---------------------------------------------------------------------------

@router.get(
    "/vozes",
    response_model=list[VozInfo],
    summary="Listar vozes PT-PT disponíveis",
)
async def listar_vozes():
    """Devolve as vozes PT-PT disponíveis para TTS."""
    return [
        VozInfo(id="raquel", nome_completo="pt-PT-RaquelNeural", genero="feminino"),
        VozInfo(id="duarte", nome_completo="pt-PT-DuarteNeural", genero="masculino"),
    ]