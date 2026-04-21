"""
Serviço de integração com a API Groq (Llama 3.3 70B).
- Responde sempre em Português de Portugal (PT-PT).
- Suporta modo streaming para baixa latência no primeiro token.
- Regista o tempo até ao primeiro token (TTFT) para monitorização.
"""

from __future__ import annotations

import time
import logging
from typing import Generator
from groq import Groq
from app.core.config import settings
from app.services.guioes import get_system_prompt as get_guiao_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt base — PT-PT empático
# ---------------------------------------------------------------------------
_BASE = (
    "Respondes SEMPRE em Português de Portugal (PT-PT), usando linguagem "
    "clara, calorosa e acessível, adequada para pessoas idosas. "
    "Sê paciente, encorajador e nunca uses jargão técnico. "
    "Quando não souberes algo, diz-o com honestidade e gentileza."
)

SYSTEM_PT_PT = f"""És um assistente conversacional empático do projeto Memórias Vivas, 
desenhado para apoiar e acompanhar pessoas idosas. {_BASE}"""

# ---------------------------------------------------------------------------
# Prompts especializados por tema
# Cada tema injeta contexto adicional no system prompt para guiar o modelo.
# ---------------------------------------------------------------------------
TEMAS: dict[str, str] = {
    "memorias": (
        f"Estás a conduzir uma conversa sobre memórias e histórias de vida. "
        f"Faz perguntas abertas e calorosas sobre a infância, família, trabalho e "
        f"momentos marcantes do utilizador. Valoriza cada recordação partilhada. {_BASE}"
    ),
    "saude": (
        f"Estás a apoiar o utilizador em temas de bem-estar e saúde. "
        f"Encoraja hábitos saudáveis, mas NUNCA dás conselhos médicos. "
        f"Sugere sempre consultar um profissional de saúde para dúvidas clínicas. {_BASE}"
    ),
    "entretenimento": (
        f"Estás a proporcionar entretenimento leve e alegre: curiosidades, "
        f"adivinhações, factos históricos interessantes, músicas populares portuguesas "
        f"e histórias curtas. Mantém o tom divertido e acessível. {_BASE}"
    ),
    "familia": (
        f"Estás a conversar sobre família, relações e pessoas queridas. "
        f"Sê especialmente empático, acolhedor e celebra os laços familiares "
        f"que o utilizador partilhar contigo. {_BASE}"
    ),
    "exercicio": (
        f"Estás a motivar o utilizador para a atividade física adaptada à sua idade. "
        f"Sugere exercícios suaves (caminhadas, alongamentos, cadeira de ginástica). "
        f"Sê encorajador e celebra qualquer pequeno progresso. {_BASE}"
    ),
    "geral": SYSTEM_PT_PT,
}


def _system_prompt(tema: str | None) -> str:
    """Devolve o system prompt correto para o tema dado (ou o base se None/inválido)."""
    if not tema:
        return SYSTEM_PT_PT
    return TEMAS.get(tema.lower().strip(), SYSTEM_PT_PT)

# ---------------------------------------------------------------------------
# Cliente Groq (inicializado uma vez, reutilizado em todos os pedidos)
# ---------------------------------------------------------------------------
_client: Optional[Groq] = None


def _get_client() -> Groq:
    """Devolve o cliente Groq, criando-o na primeira chamada (lazy init)."""
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY não está definida no ficheiro .env")
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Função principal — chat síncrono
# ---------------------------------------------------------------------------
def chat(mensagem: str, historico: Optional[list[dict]] = None, tema: Optional[str] = None) -> dict:
    """
    Envia uma mensagem ao modelo Llama 3.3 70B via Groq e devolve a resposta.

    Args:
        mensagem:  Texto do utilizador.
        historico: Lista opcional de mensagens anteriores (role/content).
        tema:      Tema da conversa (ex: 'memorias', 'saude', 'familia').

    Returns:
        dict com 'resposta' (str) e 'ttft_ms' (float — ms até ao 1.º token).
    """
    client = _get_client()

    mensagens = [{"role": "system", "content": _system_prompt(tema)}]
    if historico:
        mensagens.extend(historico)
    mensagens.append({"role": "user", "content": mensagem})

    t0 = time.perf_counter()

    resposta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.7,
        max_tokens=1024,
    )

    ttft_ms = (time.perf_counter() - t0) * 1000
    conteudo = resposta.choices[0].message.content

    logger.info(
        "Groq | modelo=%s | tokens_entrada=%d | tokens_saida=%d | ttft=%.1fms",
        resposta.model,
        resposta.usage.prompt_tokens,
        resposta.usage.completion_tokens,
        ttft_ms,
    )

    return {"resposta": conteudo, "ttft_ms": round(ttft_ms, 1), "tema": tema or "geral"}


# ---------------------------------------------------------------------------
# Função de streaming — devolve um gerador de chunks de texto
# ---------------------------------------------------------------------------
def chat_stream(mensagem: str, historico: list[dict] | None = None, tema: str | None = None) -> Generator[str, None, None]:
    """
    Versão streaming do chat. Devolve um gerador que emite chunks de texto
    à medida que o modelo os produz (Server-Sent Events).

    Uso:
        for chunk in chat_stream("Olá"):
            print(chunk, end="", flush=True)
    """
    client = _get_client()

    mensagens = [{"role": "system", "content": _system_prompt(tema)}]
    if historico:
        mensagens.extend(historico)
    mensagens.append({"role": "user", "content": mensagem})

    t0 = time.perf_counter()
    primeiro_token = True

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.7,
        max_tokens=1024,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            if primeiro_token:
                ttft_ms = (time.perf_counter() - t0) * 1000
                logger.info("Groq streaming | TTFT=%.1fms", ttft_ms)
                primeiro_token = False
            yield delta


# ---------------------------------------------------------------------------
# Funções de Entrevista GUIADA por Guioes
# ---------------------------------------------------------------------------
def entrevista_chat(mensagem: str, tema: str, perguntas_feitas: list[str] | None = None, historico: list[dict] | None = None):
    """
    Chat para modo entrevista, usando o get_system_prompt do guioes.py.
    """
    client = _get_client()
    system_prompt = get_guiao_prompt(tema, perguntas_feitas)

    mensagens = [{"role": "system", "content": system_prompt}]
    if historico:
        mensagens.extend(historico)
    mensagens.append({"role": "user", "content": mensagem})

    t0 = time.perf_counter()

    resposta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.7,
        max_tokens=1024,
    )

    ttft_ms = (time.perf_counter() - t0) * 1000
    conteudo = resposta.choices[0].message.content

    return {"resposta": conteudo, "ttft_ms": round(ttft_ms, 1), "tema": tema}


def entrevista_chat_stream(mensagem: str, tema: str, perguntas_feitas: list[str] | None = None, historico: list[dict] | None = None) -> Generator[str, None, None]:
    """
    Versão streaming para a entrevista.
    """
    client = _get_client()
    system_prompt = get_guiao_prompt(tema, perguntas_feitas)

    mensagens = [{"role": "system", "content": system_prompt}]
    if historico:
        mensagens.extend(historico)
    mensagens.append({"role": "user", "content": mensagem})

    t0 = time.perf_counter()
    primeiro_token = True

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.7,
        max_tokens=1024,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            if primeiro_token:
                ttft_ms = (time.perf_counter() - t0) * 1000
                primeiro_token = False
            yield delta
