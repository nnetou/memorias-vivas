"""
app/api/ws.py — WebSocket de conversa de voz em tempo real (Epic 5.3).

Protocolo de mensagens (JSON + binário):

  Cliente → Servidor:
    {"type": "init",  "user_id": "...", "session_id": "...|null", "tema": "...", "voz": "..."}
    <bytes>  — áudio completo da gravação (webm/mp3/wav)

  Servidor → Cliente:
    {"type": "pronto",          "session_id": "..."}
    {"type": "transcricao",     "texto": "..."}
    {"type": "resposta",        "texto": "...", "session_id": "...", "ttft_ms": ...}
    {"type": "audio_inicio"}
    <bytes>  — chunks MP3 do TTS (streaming)
    {"type": "audio_fim"}
    {"type": "pedir_repeticao", "motivo": "stt"|"ia"|"vazio"}   ← em vez de erro
    <bytes>  — MP3 da frase de pedido de repetição
    {"type": "audio_fim"}
    {"type": "erro",            "mensagem": "..."}   ← só para erros de protocolo

Ciclo de uma interação:
    1. Cliente envia init (uma vez por ligação)
    2. Cliente envia bytes de áudio
    3. Servidor: STT → texto  (falha → pedir_repeticao em voz)
    4. Servidor envia {"type":"transcricao"}
    5. Servidor: Groq → resposta  (falha → pedir_repeticao em voz)
    6. Servidor envia {"type":"resposta"}
    7. Servidor: TTS streaming → chunks MP3
    8. Servidor envia audio_inicio / <bytes> / audio_fim
    9. Ciclo repete — cliente pode enviar novo áudio
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import groq_service, profile_service
from app.services.whisper_service import transcrever
from app.services.stt_filter import filtrar as filtrar_transcricao
from app.services.tts_service import sintetizar_streaming, sintetizar, VOZ_PADRAO
from app.services.redis_service import get_historico, append_interacao

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Frases de pedido de repetição — sintetizadas em voz, nunca mostradas ao user
# ---------------------------------------------------------------------------
_FRASES_REPETICAO = {
    "stt":   "Desculpe, não consegui ouvir bem. Pode repetir, por favor?",
    "ia":    "Tive um pequeno problema. Pode repetir a sua pergunta?",
    "vazio": "Não ouvi nada. Pode falar um pouco mais alto?",
}


# ---------------------------------------------------------------------------
# Helpers de protocolo
# ---------------------------------------------------------------------------

async def _enviar_json(ws: WebSocket, dados: dict) -> None:
    await ws.send_text(json.dumps(dados, ensure_ascii=False))


async def _enviar_erro(ws: WebSocket, mensagem: str) -> None:
    """Erro de protocolo — enviado ao frontend, não ao utilizador."""
    logger.warning("WS erro de protocolo: %s", mensagem)
    await _enviar_json(ws, {"type": "erro", "mensagem": mensagem})


async def _pedir_repeticao(
    ws: WebSocket,
    motivo: str,
    voz: str,
    exc: Exception | None = None,
) -> None:
    """
    Em vez de enviar um erro técnico, sintetiza uma frase amigável em voz
    e envia {"type": "pedir_repeticao"} para o frontend reativar o microfone.

    O utilizador ouve o pedido de repetição — nunca vê uma mensagem de erro.

    Args:
        motivo: "stt" | "ia" | "vazio"
        voz:    Voz TTS a usar (a mesma da sessão)
        exc:    Exceção original — registada nos logs mas nunca enviada ao cliente
    """
    if exc:
        logger.warning("WS pedir_repeticao | motivo=%s | erro_interno=%s", motivo, exc)
    else:
        logger.info("WS pedir_repeticao | motivo=%s", motivo)

    frase = _FRASES_REPETICAO.get(motivo, _FRASES_REPETICAO["ia"])

    # Notifica o frontend para reativar o microfone
    await _enviar_json(ws, {"type": "pedir_repeticao", "motivo": motivo})

    # Sintetiza o pedido de repetição em voz
    await _enviar_json(ws, {"type": "audio_inicio"})
    try:
        async for chunk in sintetizar_streaming(frase, voz):
            await ws.send_bytes(chunk)
    except Exception as tts_exc:
        # Se o próprio TTS falhar aqui, apenas loga — não podemos fazer mais nada
        logger.error("TTS falhou no pedir_repeticao: %s", tts_exc)
    finally:
        await _enviar_json(ws, {"type": "audio_fim"})


# ---------------------------------------------------------------------------
# WebSocket /ws/conversa
# ---------------------------------------------------------------------------

@router.websocket("/conversa")
async def ws_conversa(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    """
    WebSocket de conversa de voz em tempo real.
    Ciclo: áudio → STT → Groq → TTS → MP3
    Em caso de falha no pipeline, o utilizador ouve um pedido de repetição.
    """
    await websocket.accept()
    logger.info("WebSocket ligado: %s", websocket.client)

    # Estado da sessão
    user_id: str | None = None
    session_id: str | None = None
    tema: str = "geral"
    voz: str = VOZ_PADRAO

    try:
        while True:
            message = await websocket.receive()

            # ── Mensagem de texto (controlo) ──────────────────────────────
            if "text" in message:
                try:
                    dados = json.loads(message["text"])
                except json.JSONDecodeError:
                    await _enviar_erro(websocket, "JSON inválido.")
                    continue

                tipo = dados.get("type")

                if tipo == "init":
                    user_id    = dados.get("user_id")
                    session_id = dados.get("session_id") or str(uuid.uuid4())
                    tema       = dados.get("tema", "geral")
                    voz        = dados.get("voz", VOZ_PADRAO)

                    if not user_id:
                        await _enviar_erro(websocket, "user_id obrigatório na mensagem init.")
                        continue

                    logger.info(
                        "WS init | user=%s | session=%s | tema=%s | voz=%s",
                        user_id, session_id, tema, voz,
                    )
                    await _enviar_json(websocket, {
                        "type": "pronto",
                        "session_id": session_id,
                        "mensagem": "Sessão iniciada. Pode começar a falar.",
                    })

                elif tipo == "ping":
                    await _enviar_json(websocket, {"type": "pong"})

                else:
                    await _enviar_erro(websocket, f"Tipo desconhecido: '{tipo}'")

            # ── Mensagem binária (áudio) ──────────────────────────────────
            elif "bytes" in message:
                audio_bytes = message["bytes"]

                # Erros de protocolo — não chegam ao utilizador
                if not user_id:
                    await _enviar_erro(websocket, "Enviar 'init' antes de áudio.")
                    continue

                if not audio_bytes or len(audio_bytes) == 0:
                    await _pedir_repeticao(websocket, "vazio", voz)
                    continue

                logger.info(
                    "WS áudio | user=%s | %.1f KB", user_id, len(audio_bytes) / 1024
                )

                # ── 1. STT ────────────────────────────────────────────────
                try:
                    loop = asyncio.get_event_loop()
                    resultado_stt = await loop.run_in_executor(
                        None,
                        lambda: transcrever(
                            audio_bytes=audio_bytes,
                            filename="gravacao.webm",
                            prompt_hint=f"tema: {tema}",
                        ),
                    )
                    texto_utilizador = resultado_stt.texto.strip()
                except Exception as exc:
                    await _pedir_repeticao(websocket, "stt", voz, exc)
                    continue

                if not texto_utilizador:
                    await _pedir_repeticao(websocket, "vazio", voz)
                    continue

                # ── Filtro STT — avalia gravidade e corrige em silêncio ────
                resultado_filtro = await loop.run_in_executor(
                    None,
                    lambda: filtrar_transcricao(texto_utilizador),
                )
                texto_para_groq = resultado_filtro.texto_final
                # Envia sempre o texto original ao frontend (o utilizador vê o que disse)
                # O Groq recebe o texto filtrado (pode ser diferente, mas o user não sabe)
                await _enviar_json(websocket, {
                    "type": "transcricao",
                    "texto": texto_utilizador,
                })
                logger.info(
                    "WS STT OK | user=%s | original='%s'%s",
                    user_id,
                    texto_utilizador[:80],
                    f" | corrigido='{texto_para_groq[:80]}'" if resultado_filtro.foi_corrigido else "",
                )

                # ── 2. Groq ───────────────────────────────────────────────
                historico = await get_historico(session_id)
                perfil_db = await profile_service.get_profile(user_id, db)

                try:
                    loop = asyncio.get_event_loop()
                    if perfil_db:
                        temas_anteriores = await profile_service.get_temas_explorados(
                            user_id, db
                        )
                        resultado_groq = await loop.run_in_executor(
                            None,
                            lambda: groq_service.conversa_personalizada(
                                mensagem=texto_para_groq,
                                tema=tema,
                                perfil_json=perfil_db.perfil_json,
                                temas_anteriores=temas_anteriores,
                                historico=historico,
                            ),
                        )
                    else:
                        resultado_groq = await loop.run_in_executor(
                            None,
                            lambda: groq_service.chat(
                                mensagem=texto_para_groq,
                                historico=historico,
                                tema=tema,
                            ),
                        )
                except Exception as exc:
                    await _pedir_repeticao(websocket, "ia", voz, exc)
                    continue

                texto_assistente = resultado_groq["resposta"]

                await _enviar_json(websocket, {
                    "type": "resposta",
                    "texto": texto_assistente,
                    "session_id": session_id,
                    "ttft_ms": resultado_groq.get("ttft_ms"),
                })

                # Persiste no Redis
                await append_interacao(session_id, texto_para_groq, texto_assistente)

                # ── 3. TTS ────────────────────────────────────────────────
                await _enviar_json(websocket, {"type": "audio_inicio"})
                tts_ok = True
                try:
                    async for chunk in sintetizar_streaming(texto_assistente, voz):
                        await websocket.send_bytes(chunk)
                except Exception as exc:
                    # TTS falhou a meio — pede repetição mas o texto já foi enviado
                    logger.error("WS TTS falhou: %s", exc)
                    tts_ok = False
                finally:
                    await _enviar_json(websocket, {"type": "audio_fim"})

                if not tts_ok:
                    # Texto já foi entregue via {"type":"resposta"} — frontend pode mostrá-lo
                    # Pedimos repetição apenas para o ciclo seguinte
                    await _pedir_repeticao(websocket, "ia", voz)

                logger.info("WS ciclo OK | user=%s | session=%s", user_id, session_id)

    except WebSocketDisconnect:
        logger.info("WS desligado | user=%s | session=%s", user_id, session_id)
    except Exception as exc:
        logger.exception("WS erro inesperado: %s", exc)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass