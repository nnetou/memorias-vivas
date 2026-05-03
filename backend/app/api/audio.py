"""
app/api/audio.py — Endpoints de voz para o projeto Memórias Vivas.

Endpoints:
    POST /api/v1/audio/transcrever   → STT: áudio → texto (Whisper Large V3)

Epic 5.1 — Speech-to-Text com Whisper Large V3 (Groq)
Epic 5.2 — Text-to-Speech (a implementar)
Epic 5.3 — WebSocket em tempo real (a implementar)
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.whisper_service import (
    EXTENSOES_SUPORTADAS,
    FORMATOS_SUPORTADOS,
    MAX_AUDIO_BYTES,
    transcrever,
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


# ---------------------------------------------------------------------------
# POST /transcrever
# ---------------------------------------------------------------------------

@router.post(
    "/transcrever",
    response_model=TranscricaoResponse,
    summary="Transcrever áudio para texto (Whisper Large V3)",
)
async def transcrever_audio(
    audio: UploadFile = File(
        ...,
        description="Ficheiro de áudio. Formatos: mp3, wav, webm, ogg, flac, m4a, mp4.",
    ),
    prompt_hint: str | None = Form(
        default=None,
        description=(
            "Contexto opcional para melhorar precisão "
            "(ex: nome do utilizador, tema da conversa)."
        ),
    ),
):
    """
    Transcreve um ficheiro de áudio para texto em PT-PT usando o Whisper Large V3 da Groq.

    Aceita uploads multipart/form-data com o campo `audio`.
    O campo `prompt_hint` é opcional e melhora a precisão em nomes e termos específicos.

    **Como testar no Postman:**
    - Method: POST
    - Body: form-data
    - Key `audio` (tipo File): selecionar ficheiro de áudio
    - Key `prompt_hint` (tipo Text, opcional): ex. "Manuel Silva, Évora, carpinteiro"

    **Limites:**
    - Tamanho máximo: 25 MB
    - Formatos: mp3, wav, webm, ogg, flac, m4a, mp4, mpeg
    """
    # Validar extensão / content-type
    filename = audio.filename or "audio.webm"
    extensao = os.path.splitext(filename)[1].lower()
    content_type = (audio.content_type or "").lower()

    formato_valido = (
        content_type in FORMATOS_SUPORTADOS
        or extensao in EXTENSOES_SUPORTADAS
        or content_type == "application/octet-stream"  # browsers genéricos
    )

    if not formato_valido:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Formato não suportado: '{content_type}' / '{extensao}'. "
                f"Formatos aceites: {', '.join(sorted(EXTENSOES_SUPORTADAS))}"
            ),
        )

    # Ler bytes
    audio_bytes = await audio.read()

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Ficheiro demasiado grande: {len(audio_bytes)/1024/1024:.1f} MB (máximo: 25 MB).",
        )

    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Ficheiro de áudio vazio.")

    logger.info(
        "STT request | ficheiro=%s | content_type=%s | tamanho=%.1f KB | hint=%s",
        filename, content_type, len(audio_bytes) / 1024, prompt_hint,
    )

    # Transcrever
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