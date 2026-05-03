"""
app/services/stt_filter.py — Filtro silencioso de transcrições STT.

Avalia a gravidade dos erros de transcrição e decide se corrige ou ignora.
O utilizador NUNCA é informado de qualquer correção — o filtro é invisível.

Gravidade 1 — IGNORAR:
    Sotaque regional, hesitações ("ah", "hm"), pontuação errada,
    palavras regionais portuguesas, frases incompletas mas compreensíveis.
    → devolve o texto original intacto

Gravidade 2 — CORRIGIR em silêncio:
    Palavras claramente cortadas que mudam o sentido, brasileirismos
    introduzidos pelo Whisper (ex: "você" → "o senhor"), transcrição
    obviamente incorreta que confundiria o Groq.
    → devolve texto corrigido sem avisar o utilizador

Regra fundamental:
    Em caso de dúvida, IGNORAR — é sempre melhor o Groq receber
    texto imperfeito do que o utilizador sentir que está a ser corrigido.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cliente Groq (singleton)
# ---------------------------------------------------------------------------
_client: Groq | None = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Resultado do filtro
# ---------------------------------------------------------------------------

@dataclass
class ResultadoFiltro:
    texto_final: str          # texto a enviar ao Groq
    foi_corrigido: bool       # True se foi alterado (só para logs internos)
    texto_original: str       # sempre guardado para debug


# ---------------------------------------------------------------------------
# Prompt de avaliação — conciso para baixa latência
# ---------------------------------------------------------------------------

_PROMPT_FILTRO = """\
Analisa esta transcrição de voz de uma pessoa idosa portuguesa e decide o que fazer.

TRANSCRIÇÃO: "{texto}"

Regras de decisão:
- IGNORAR se: sotaque regional, hesitações (ah, hm, é, pronto), pontuação estranha, \
frases curtas ou incompletas mas compreensíveis, palavras regionais portuguesas.
- CORRIGIR se: palavras obviamente cortadas que mudam o sentido, brasileirismos \
introduzidos pelo sistema de transcrição (ex: "você" deve ser "o senhor/a senhora"), \
texto completamente incoerente que a IA não conseguiria responder.

Em caso de dúvida: IGNORAR.

Responde APENAS com um destes dois formatos — nada mais:
IGNORAR
ou
CORRIGIR: <texto corrigido>
"""


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def filtrar(texto: str) -> ResultadoFiltro:
    """
    Avalia e opcionalmente corrige uma transcrição STT.

    Usa o Groq com temperatura 0 para decisão determinística.
    Chamada síncrona — correr em executor no contexto async.

    Args:
        texto: Transcrição bruta do Whisper.

    Returns:
        ResultadoFiltro com o texto final a enviar ao Groq.
        Em caso de falha do filtro, devolve sempre o texto original.
    """
    if not texto or not texto.strip():
        return ResultadoFiltro(
            texto_final=texto,
            foi_corrigido=False,
            texto_original=texto,
        )

    # Textos muito curtos (1-2 palavras) — nunca corrigir
    if len(texto.split()) <= 2:
        logger.debug("Filtro STT | texto curto — ignorar automaticamente")
        return ResultadoFiltro(
            texto_final=texto,
            foi_corrigido=False,
            texto_original=texto,
        )

    try:
        resposta = _get_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "És um avaliador de transcrições de voz. "
                        "Respondes APENAS com 'IGNORAR' ou 'CORRIGIR: <texto>'. "
                        "Sem explicações, sem mais nada."
                    ),
                },
                {
                    "role": "user",
                    "content": _PROMPT_FILTRO.format(texto=texto),
                },
            ],
            temperature=0.0,
            max_tokens=200,
        )

        raw = resposta.choices[0].message.content.strip()

        if raw.upper().startswith("CORRIGIR:"):
            texto_corrigido = raw[len("CORRIGIR:"):].strip()

            # Segurança: se a correção for vazia ou muito diferente, ignorar
            if not texto_corrigido or len(texto_corrigido) < 3:
                logger.debug("Filtro STT | correção inválida — a usar original")
                return ResultadoFiltro(
                    texto_final=texto,
                    foi_corrigido=False,
                    texto_original=texto,
                )

            logger.info(
                "Filtro STT | CORRIGIDO silenciosamente | original='%s' | corrigido='%s'",
                texto[:80], texto_corrigido[:80],
            )
            return ResultadoFiltro(
                texto_final=texto_corrigido,
                foi_corrigido=True,
                texto_original=texto,
            )

        # IGNORAR ou qualquer outra resposta — devolve original
        logger.debug("Filtro STT | IGNORAR | '%s'", texto[:80])
        return ResultadoFiltro(
            texto_final=texto,
            foi_corrigido=False,
            texto_original=texto,
        )

    except Exception as exc:
        # Falha no filtro — nunca bloquear a conversa, devolve sempre o original
        logger.warning("Filtro STT falhou (a usar original): %s", exc)
        return ResultadoFiltro(
            texto_final=texto,
            foi_corrigido=False,
            texto_original=texto,
        )