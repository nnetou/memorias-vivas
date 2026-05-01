"""
groq_service.py — Integração com a API Groq (Llama 3.3 70B).

Modos de operação:
    chat()                      → resposta genérica (PT-PT)
    chat_stream()               → idem, em streaming
    conversa_personalizada()    → pergunta dinâmica baseada em tema + perfil do idoso
    conversa_personalizada_stream() → idem, em streaming
"""

from __future__ import annotations

import json
import time
import logging
from typing import Generator, Optional

from groq import Groq
from app.core.config import settings

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

SYSTEM_PT_PT = (
    f"És um assistente conversacional empático do projeto Memórias Vivas, "
    f"desenhado para apoiar e acompanhar pessoas idosas. {_BASE}"
)

# ---------------------------------------------------------------------------
# System prompt dinâmico — sem guiões fixos (Epic 2.4)
# Gerado em runtime com base no tema, perfil biográfico e temas já explorados.
# ---------------------------------------------------------------------------
_SYSTEM_DINAMICO_TEMPLATE = """\
És o assistente Memórias Vivas — empático, paciente e caloroso.
Conduzes conversas em Português de Portugal (PT-PT) com pessoas idosas.

════════════════════════════════════════
MEMÓRIA BIOGRÁFICA — FACTOS JÁ CONHECIDOS SOBRE ESTA PESSOA:
{perfil_json}
════════════════════════════════════════

IMPORTANTE: Os factos acima NÃO são novidade — já os conheces de sessões anteriores.
Usa-os ACTIVAMENTE na conversa:
  • Trata a pessoa pelo nome se estiver disponível no perfil.
  • Faz referências naturais ao passado: "Como me contou antes...", "Lembro-me que disse que...".
  • Nunca digas que não tens memória ou que é a primeira vez que falas com esta pessoa.
  • Nunca peças informações que já constam no perfil acima.

Tema actual: {tema}
Temas já explorados: {temas_anteriores}

REGRAS DE CONVERSA:
1. Faz SEMPRE apenas UMA pergunta de cada vez. Nunca duas.
2. Personaliza cada pergunta com base nos factos do perfil acima.
3. Não repitas temas já explorados.
4. Usa linguagem simples, frases curtas e tom caloroso.
5. Confirma o que ouviste antes de colocar a próxima pergunta.
6. Nunca inventes factos que NÃO estejam no perfil.
7. Se o utilizador ficar emocionado, reconhece com empatia antes de continuar.
8. Fala sempre em PT-PT. Evita expressões do Brasil.
"""


def _build_dynamic_system_prompt(
    tema: str,
    perfil_json: dict | None,
    temas_anteriores: list[str] | None,
) -> str:
    """Constrói o system prompt dinâmico injectando o perfil em linguagem natural."""
    perfil_str = _perfil_para_texto(perfil_json)
    temas_str = ", ".join(temas_anteriores or []) or "nenhum"
    return _SYSTEM_DINAMICO_TEMPLATE.format(
        tema=tema,
        perfil_json=perfil_str,
        temas_anteriores=temas_str,
    )


def _perfil_para_texto(perfil: dict | None) -> str:
    """
    Converte o perfil biográfico em texto legível em vez de JSON cru.
    O Llama interpreta prosa de forma muito mais fiável do que JSON.
    """
    if not perfil:
        return "(sem dados biográficos disponíveis)"

    linhas = []
    if perfil.get("nome"):
        linhas.append(f"• Nome: {perfil['nome']}")
    if perfil.get("terra_natal"):
        linhas.append(f"• Terra natal: {perfil['terra_natal']}")
    if perfil.get("profissao"):
        linhas.append(f"• Profissão: {perfil['profissao']}")
    if perfil.get("familia"):
        linhas.append(f"• Família: {perfil['familia']}")
    if perfil.get("memoria_marcante"):
        linhas.append(f"• Memória marcante: {perfil['memoria_marcante']}")

    # Campos extra em "outros" (schema rico do merge)
    outros = perfil.get("outros") or {}
    for chave, valor in outros.items():
        if valor:
            linhas.append(f"• {chave.replace('_', ' ').capitalize()}: {valor}")

    return "\n".join(linhas) if linhas else "(sem dados biográficos disponíveis)"


# ---------------------------------------------------------------------------
# Prompts especializados por tema (modo genérico / sem perfil)
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
    """Devolve o system prompt correcto para o tema dado (ou o base se None/inválido)."""
    if not tema:
        return SYSTEM_PT_PT
    return TEMAS.get(tema.lower().strip(), SYSTEM_PT_PT)


# ---------------------------------------------------------------------------
# Cliente Groq (lazy init, reutilizado em todos os pedidos)
# ---------------------------------------------------------------------------
_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY não está definida no ficheiro .env")
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# chat() — resposta genérica completa
# ---------------------------------------------------------------------------
def chat(
    mensagem: str,
    historico: Optional[list[dict]] = None,
    tema: Optional[str] = None,
) -> dict:
    """
    Envia uma mensagem ao Llama 3.3 70B e devolve a resposta completa.

    Returns:
        {"resposta": str, "ttft_ms": float, "tema": str}
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
# chat_stream() — streaming genérico
# ---------------------------------------------------------------------------
def chat_stream(
    mensagem: str,
    historico: list[dict] | None = None,
    tema: str | None = None,
) -> Generator[str, None, None]:
    """Versão streaming do chat genérico. Emite chunks de texto."""
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
# conversa_personalizada() — pergunta dinâmica baseada no perfil (Epic 2.4)
# ---------------------------------------------------------------------------
def conversa_personalizada(
    mensagem: str,
    tema: str,
    perfil_json: dict | None = None,
    temas_anteriores: list[str] | None = None,
    historico: list[dict] | None = None,
) -> dict:
    """
    Gera a próxima pergunta personalizada com base no perfil biográfico do idoso.

    Args:
        mensagem:          Resposta mais recente do utilizador.
        tema:              Tema da conversa actual (ex: "infancia", "trabalho").
        perfil_json:       Perfil biográfico extraído pelo Gemini no onboarding.
        temas_anteriores:  Temas já explorados em sessões anteriores.
        historico:         Histórico da sessão actual.

    Returns:
        {"resposta": str, "ttft_ms": float, "tema": str}
    """
    client = _get_client()
    system = _build_dynamic_system_prompt(tema, perfil_json, temas_anteriores)

    mensagens = [{"role": "system", "content": system}]
    if historico:
        mensagens.extend(historico)
    mensagens.append({"role": "user", "content": mensagem})

    t0 = time.perf_counter()
    resposta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.75,
        max_tokens=512,
    )
    ttft_ms = (time.perf_counter() - t0) * 1000
    conteudo = resposta.choices[0].message.content

    logger.info(
        "Groq dinâmico | tema=%s | ttft=%.1fms",
        tema,
        ttft_ms,
    )
    return {"resposta": conteudo, "ttft_ms": round(ttft_ms, 1), "tema": tema}


# ---------------------------------------------------------------------------
# conversa_personalizada_stream() — versão streaming
# ---------------------------------------------------------------------------
def conversa_personalizada_stream(
    mensagem: str,
    tema: str,
    perfil_json: dict | None = None,
    temas_anteriores: list[str] | None = None,
    historico: list[dict] | None = None,
) -> Generator[str, None, None]:
    """
    Versão streaming da conversa personalizada.
    Emite chunks de texto à medida que o modelo os produz.
    """
    client = _get_client()
    system = _build_dynamic_system_prompt(tema, perfil_json, temas_anteriores)

    mensagens = [{"role": "system", "content": system}]
    if historico:
        mensagens.extend(historico)
    mensagens.append({"role": "user", "content": mensagem})

    t0 = time.perf_counter()
    primeiro_token = True

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensagens,
        temperature=0.75,
        max_tokens=512,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            if primeiro_token:
                ttft_ms = (time.perf_counter() - t0) * 1000
                logger.info("Groq dinâmico streaming | tema=%s | TTFT=%.1fms", tema, ttft_ms)
                primeiro_token = False
            yield delta