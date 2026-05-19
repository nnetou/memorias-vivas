"""
app/services/stt_normalizer.py — Normalizador fonético de transcrições STT.

Posição no pipeline:
    Áudio → Whisper → [Normalizador] → Groq principal → TTS

Responsabilidade única:
    Corrigir erros fonéticos óbvios em transcrições PT-PT sem alterar
    o significado. Usa o llama-3.1-8b-instant (modelo pequeno e rápido) para
    minimizar impacto na latência do WebSocket.

Características:
    - Modelo: llama-3.1-8b-instant (~100ms, baixo custo)
    - Fallback: se falhar, devolve sempre o texto original
    - Nunca altera o significado, só corrige a forma fonética
    - Não deteta alucinações (isso é feito antes desta camada)

Exemplos de correções esperadas:
    "Liria"     → "Leiria"
    "basoura"   → "vassoura"
    "Figuera"   → "Figueira"
    "alentejo"  → "Alentejo"
    "trabalhei na lavoira" → "trabalhei na lavoura"
"""

from __future__ import annotations

import logging
import time

from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

_MODELO = "llama-3.1-8b-instant"   # modelo rápido e leve — propositado para esta tarefa

_SYSTEM_NORMALIZER = """\
És um corretor fonético rigoroso de Português de Portugal (PT-PT).

Recebes um texto transcrito automaticamente por um sistema de voz (STT/Whisper) \
a partir da fala de uma pessoa idosa portuguesa.

O teu ÚNICO objetivo é corrigir erros fonéticos óbvios introduzidos pelo sistema \
de transcrição, como:
- Nomes de localidades portuguesas mal transcritos (ex: "Liria" → "Leiria", \
"Figuera" → "Figueira", "Setubel" → "Setúbal")
- Palavras portuguesas com erros fonéticos (ex: "basoura" → "vassoura", \
"lavoira" → "lavoura", "carpincia" → "carpintaria")
- Nomes próprios portugueses comuns mal transcritos
- Acentuação óbvia em falta por erro de transcrição

REGRAS ABSOLUTAS:
- NÃO respondas à mensagem nem à pergunta implícita no texto.
- NÃO acrescentes palavras, explicações ou pontuação extra.
- NÃO alteres o significado, a estrutura da frase nem o vocabulário escolhido.
- Se o texto estiver correto, devolve-o EXATAMENTE igual.
- Devolve APENAS a frase corrigida — nada mais.
"""

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
# API pública
# ---------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """
    Corrige erros fonéticos numa transcrição Whisper usando llama3-8b.

    Síncrono — chamar com run_in_executor em contexto async.

    Args:
        texto: Transcrição bruta do Whisper.

    Returns:
        Texto corrigido. Em caso de falha, devolve o texto original intacto.
    """
    if not texto or len(texto.strip()) < 3:
        return texto

    t0 = time.perf_counter()
    try:
        resposta = _get_client().chat.completions.create(
            model=_MODELO,
            messages=[
                {"role": "system", "content": _SYSTEM_NORMALIZER},
                {"role": "user",   "content": texto},
            ],
            temperature=0.0,   # determinístico — só corrige, não cria
            max_tokens=256,
        )

        corrigido = resposta.choices[0].message.content.strip()
        latencia  = (time.perf_counter() - t0) * 1000

        if corrigido != texto:
            logger.info(
                "STT normalizer | %.0fms | '%s' → '%s'",
                latencia, texto[:60], corrigido[:60],
            )
        else:
            logger.debug("STT normalizer | %.0fms | sem alterações", latencia)

        # Segurança: se o modelo devolver algo muito diferente do original,
        # pode ter "respondido" em vez de corrigir — usar original como fallback
        if len(corrigido) > len(texto) * 2.5:
            logger.warning(
                "STT normalizer | resposta suspeita (muito longa) — a usar original"
            )
            return texto

        return corrigido or texto

    except Exception as exc:
        logger.warning("STT normalizer falhou (%s) — a usar original", exc)
        return texto

# ---------------------------------------------------------------------------
# Reformulação empática — reescreve a última frase do assistente
# ---------------------------------------------------------------------------

_SYSTEM_REPETICAO = """És a Raquel, assistente virtual do projeto Memórias Vivas (PT-PT), que apoia idosos.
O utilizador não respondeu ou o microfone falhou.
A tua tarefa é reescrever a última pergunta/frase de forma natural e empática.

REGRAS:
- Pede desculpa brevemente de forma calorosa (ex: "Peço desculpa, não consegui ouvir bem").
- Reformula a pergunta de forma direta e concisa.
- ELIMINA qualquer saudação inicial, apresentação ou "Olá/Tudo bem" da frase original.
- Mantém o foco na pergunta — nada mais.
- Fala sempre em PT-PT. Nunca uses "você".
- Devolve APENAS a frase reformulada — sem explicações, sem aspas.
"""

def gerar_repeticao_empatica(ultima_frase: str) -> str:
    """
    Reescreve a última frase do assistente de forma empática quando
    o utilizador não respondeu ou o áudio falhou.

    Usa llama-3.1-8b-instant com temperatura ligeiramente criativa (0.3)
    para evitar repetição mecânica entre chamadas.

    Exemplos:
        "Olá, chamo-me Raquel. Como se chama?"
        → "Peço desculpa, não consegui ouvir. Como é que se chama?"

        "O senhor disse que trabalhou nas minas. Como era o ambiente lá?"
        → "Desculpe, o som falhou. O que me dizia sobre o ambiente nas minas?"

    Args:
        ultima_frase: Última mensagem dita pelo assistente.

    Returns:
        Frase reformulada. Fallback para frase genérica em caso de erro.
    """
    if not ultima_frase or not ultima_frase.strip():
        return "Peço desculpa, não consegui ouvir. Pode repetir, por favor?"

    try:
        resposta = _get_client().chat.completions.create(
            model=_MODELO,
            messages=[
                {"role": "system",  "content": _SYSTEM_REPETICAO},
                {"role": "user",    "content": ultima_frase},
            ],
            temperature=0.3,
            max_tokens=150,
        )

        reformulada = resposta.choices[0].message.content.strip().strip('"').strip("'")

        if not reformulada or len(reformulada) < 5:
            raise ValueError("Resposta inválida")

        logger.info(
            "Reformulação empática | '%s...' → '%s...'",
            ultima_frase[:40], reformulada[:40],
        )
        return reformulada

    except Exception as exc:
        logger.warning("gerar_repeticao_empatica falhou (%s) — fallback genérico", exc)
        return "Peço desculpa, não consegui ouvir bem. Pode repetir?"