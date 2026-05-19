"""
app/services/tts_service.py — Text-to-Speech via edge-tts (Microsoft Neural TTS).

Porque edge-tts em vez de pyttsx3/gTTS:
    - Vozes neurais PT-PT de alta qualidade (RaquelNeural, DuarteNeural)
    - Async nativo — não bloqueia o event loop do FastAPI
    - Sem API key — usa infraestrutura do Microsoft Edge gratuitamente
    - Funciona em Docker/Linux sem dependências de sistema (espeak, etc.)

Vozes PT-PT disponíveis:
    pt-PT-RaquelNeural   → feminina, clara, adequada para assistente
    pt-PT-DuarteNeural   → masculina, pausada, boa para leitura

API pública:
    sintetizar(texto, voz)          → bytes MP3
    sintetizar_streaming(texto, voz) → AsyncGenerator[bytes]
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

import httpx
import edge_tts
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração de vozes
# ---------------------------------------------------------------------------
VOZ_PADRAO = "pt-PT-RaquelNeural"
VOZES_DISPONIVEIS = {
    "raquel":  "pt-PT-RaquelNeural",   # feminina — voz padrão do assistente
    "duarte":  "pt-PT-DuarteNeural",   # masculina
}

# Parâmetros de prosódia — fala mais pausada para idosos
RATE  = "-10%"   # ligeiramente mais lento que o padrão
PITCH = "+0Hz"   # tom neutro


# ---------------------------------------------------------------------------
# ElevenLabs Helpers
# ---------------------------------------------------------------------------

async def _sintetizar_elevenlabs(texto: str) -> bytes:
    voice_id = settings.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=body, headers=headers, timeout=30.0)
        if response.status_code != 200:
            raise RuntimeError(f"ElevenLabs TTS failed: {response.status_code} - {response.text}")
        return response.content


async def _sintetizar_streaming_elevenlabs(texto: str) -> AsyncGenerator[bytes, None]:
    voice_id = settings.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=body, headers=headers, timeout=30.0) as response:
            if response.status_code != 200:
                raise RuntimeError(f"ElevenLabs TTS stream failed: {response.status_code}")
            async for chunk in response.aiter_bytes():
                yield chunk


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

async def sintetizar(
    texto: str,
    voz: str = VOZ_PADRAO,
) -> bytes:
    """
    Converte texto em áudio MP3 em PT-PT.
    Se ELEVENLABS_API_KEY estiver configurada, usa ElevenLabs.
    Caso contrário, ou em caso de erro, usa edge-tts como fallback robusto.
    """
    if not texto or not texto.strip():
        raise ValueError("Texto vazio — nada a sintetizar.")

    # ── Tentativa 1: ElevenLabs (se API Key configurada) ──────────────────
    if settings.ELEVENLABS_API_KEY:
        try:
            logger.info("TTS ElevenLabs | chars=%d | voice_id=%s", len(texto), settings.ELEVENLABS_VOICE_ID)
            return await _sintetizar_elevenlabs(texto)
        except Exception as exc:
            logger.warning("ElevenLabs falhou (%s) — a usar edge-tts como fallback.", exc)

    # ── Tentativa 2: edge-tts (Padrão / Fallback) ─────────────────────────
    # Resolver nome curto → nome completo
    voz_resolvida = VOZES_DISPONIVEIS.get(voz.lower(), voz)

    logger.info(
        "TTS edge-tts | voz=%s | chars=%d",
        voz_resolvida, len(texto),
    )

    try:
        communicate = edge_tts.Communicate(
            text=texto,
            voice=voz_resolvida,
            rate=RATE,
            pitch=PITCH,
        )

        # Acumula todos os chunks de áudio em memória
        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        audio_bytes = b"".join(audio_chunks)

        logger.info(
            "TTS edge-tts concluído | voz=%s | tamanho=%.1f KB",
            voz_resolvida, len(audio_bytes) / 1024,
        )
        return audio_bytes

    except Exception as exc:
        logger.exception("Erro no TTS: %s", exc)
        raise RuntimeError(f"Síntese de voz falhou: {exc}") from exc


async def sintetizar_streaming(
    texto: str,
    voz: str = VOZ_PADRAO,
) -> AsyncGenerator[bytes, None]:
    """
    Versão streaming — emite chunks de áudio MP3 à medida que são gerados.
    Se ELEVENLABS_API_KEY estiver configurada, usa ElevenLabs.
    Caso contrário, ou em caso de erro, usa edge-tts como fallback robusto.
    """
    if not texto or not texto.strip():
        raise ValueError("Texto vazio.")

    # ── Tentativa 1: ElevenLabs (se API Key configurada) ──────────────────
    if settings.ELEVENLABS_API_KEY:
        try:
            logger.info("TTS ElevenLabs Streaming | chars=%d", len(texto))
            async for chunk in _sintetizar_streaming_elevenlabs(texto):
                yield chunk
            return
        except Exception as exc:
            logger.warning("ElevenLabs Streaming falhou (%s) — a usar edge-tts como fallback.", exc)

    # ── Tentativa 2: edge-tts (Padrão / Fallback) ─────────────────────────
    voz_resolvida = VOZES_DISPONIVEIS.get(voz.lower(), voz)

    communicate = edge_tts.Communicate(
        text=texto,
        voice=voz_resolvida,
        rate=RATE,
        pitch=PITCH,
    )

    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
    except Exception as exc:
        logger.exception("Erro no TTS streaming: %s", exc)
        raise RuntimeError(f"Síntese de voz (stream) falhou: {exc}") from exc