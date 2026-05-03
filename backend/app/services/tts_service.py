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

import edge_tts

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
# API pública
# ---------------------------------------------------------------------------

async def sintetizar(
    texto: str,
    voz: str = VOZ_PADRAO,
) -> bytes:
    """
    Converte texto em áudio MP3 em PT-PT.

    Args:
        texto: Texto a sintetizar (máximo recomendado: 5000 caracteres).
        voz:   Nome da voz (ex: "raquel", "duarte") ou nome completo
               do modelo edge-tts (ex: "pt-PT-RaquelNeural").

    Returns:
        Bytes do ficheiro MP3 pronto a enviar ao cliente.

    Raises:
        RuntimeError: Falha na comunicação com o serviço edge-tts.
    """
    if not texto or not texto.strip():
        raise ValueError("Texto vazio — nada a sintetizar.")

    # Resolver nome curto → nome completo
    voz_resolvida = VOZES_DISPONIVEIS.get(voz.lower(), voz)

    logger.info(
        "TTS | voz=%s | chars=%d",
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
            "TTS concluído | voz=%s | tamanho=%.1f KB",
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
    Útil para o WebSocket (Epic 5.3) para reduzir latência percebida.

    Yields:
        Chunks de bytes MP3.
    """
    if not texto or not texto.strip():
        raise ValueError("Texto vazio.")

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