"""
app/services/whisper_service.py — Speech-to-Text via Groq Whisper Large V3.

Responsabilidades:
    - Receber ficheiro de áudio em bytes + formato
    - Enviar à API Groq Whisper Large V3
    - Devolver transcrição em PT-PT

Formatos suportados pelo Groq Whisper:
    mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg, flac

Limites Groq:
    - Tamanho máximo: 25 MB por ficheiro
    - Duração máxima recomendada: 10 minutos

API pública:
    transcrever(audio_bytes, filename, prompt_hint) → TranscricaoResult
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass

from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
WHISPER_MODEL = "whisper-large-v3"
AUDIO_LANGUAGE = "pt"                  # força PT — evita deteção errada para sotaques
MAX_AUDIO_BYTES = 25 * 1024 * 1024    # 25 MB — limite da API Groq

FORMATOS_SUPORTADOS = {
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/wav",
    "audio/webm", "audio/ogg", "audio/flac", "audio/m4a",
    "video/mp4", "video/webm",   # browsers enviam webm/mp4 pelo MediaRecorder
}

# Extensões aceites quando o content-type não está disponível
EXTENSOES_SUPORTADAS = {
    ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a",
    ".wav", ".webm", ".ogg", ".flac",
}

# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class TranscricaoResult:
    texto: str
    duracao_ms: float
    modelo: str = WHISPER_MODEL
    idioma: str = AUDIO_LANGUAGE


# ---------------------------------------------------------------------------
# Cliente Groq (singleton — reutiliza o padrão do groq_service)
# ---------------------------------------------------------------------------
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY não está configurada.")
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def transcrever(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    prompt_hint: str | None = None,
) -> TranscricaoResult:
    """
    Transcreve um ficheiro de áudio para texto em PT-PT usando Whisper Large V3.

    Args:
        audio_bytes:  Conteúdo do ficheiro de áudio em bytes.
        filename:     Nome do ficheiro com extensão — usado pelo Groq para
                      inferir o formato (ex: "gravacao.webm", "voz.mp3").
        prompt_hint:  Texto opcional para guiar a transcrição (ex: nome do idoso,
                      contexto da conversa). Melhora a precisão em vocabulário específico.

    Returns:
        TranscricaoResult com o texto transcrito e metadados.

    Raises:
        ValueError: Ficheiro demasiado grande ou formato não suportado.
        RuntimeError: Falha na API Groq.
    """
    # Validação de tamanho
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError(
            f"Ficheiro demasiado grande: {len(audio_bytes) / 1024 / 1024:.1f} MB "
            f"(máximo: 25 MB)"
        )

    if len(audio_bytes) == 0:
        raise ValueError("Ficheiro de áudio vazio.")

    # Construir o prompt de contexto — melhora precisão em nomes e lugares PT
    prompt = (
        "Transcrição de conversa em Português de Portugal com pessoa idosa. "
        "Preservar nomes próprios, localidades e expressões regionais portuguesas."
    )
    if prompt_hint:
        prompt += f" Contexto adicional: {prompt_hint}"

    logger.info(
        "Whisper STT | ficheiro=%s | tamanho=%.1f KB",
        filename, len(audio_bytes) / 1024,
    )

    t0 = time.perf_counter()
    try:
        transcricao = _get_client().audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=(filename, io.BytesIO(audio_bytes)),
            language=AUDIO_LANGUAGE,
            response_format="text",
            prompt=prompt,
        )
    except Exception as exc:
        logger.exception("Erro na API Groq Whisper: %s", exc)
        raise RuntimeError(f"Transcrição falhou: {exc}") from exc

    duracao_ms = (time.perf_counter() - t0) * 1000

    # A API devolve string diretamente quando response_format="text"
    texto = transcricao.strip() if isinstance(transcricao, str) else transcricao.text.strip()

    logger.info(
        "Whisper STT | transcrição concluída | chars=%d | duracao=%.0fms",
        len(texto), duracao_ms,
    )

    return TranscricaoResult(
        texto=texto,
        duracao_ms=round(duracao_ms, 1),
    )