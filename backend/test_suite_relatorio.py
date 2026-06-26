"""
test_suite_relatorio.py — Suite de testes COMPLETA para o relatório do projeto.

Cobre:
  1. Testes de Implementação  — verifica stack de software (DB, Redis, APIs)
  2. Testes Funcionais        — auth, onboarding, chat, memória, artefactos
  3. Testes de Desempenho     — latência medida, TTFT, throughput

Uso:
    docker exec memorias_vivas_api python test_suite_relatorio.py
    docker exec memorias_vivas_api python test_suite_relatorio.py --categoria implementacao
    docker exec memorias_vivas_api python test_suite_relatorio.py --categoria funcional
    docker exec memorias_vivas_api python test_suite_relatorio.py --categoria desempenho

Saída:
    - Relatório formatado no terminal (tabelas)
    - Ficheiro JSON em /app/relatorio_testes.json com todos os valores
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"
API_URL  = f"{BASE_URL}/api/v1"

TEST_EMAIL_IDOSO    = "manuel@memoriasvivas.pt"
TEST_PASS_IDOSO     = "Manuel123"
TEST_EMAIL_ADMIN    = "admin@memoriasvivas.pt"
TEST_PASS_ADMIN     = "Admin123"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estruturas de resultado
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    id: str
    categoria: str       # implementacao, funcional, desempenho
    subcategoria: str    # auth, onboarding, chat, etc.
    nome: str
    passou: bool
    detalhes: str = ""
    latencia_ms: float | None = None
    metricas: dict = field(default_factory=dict)


@dataclass
class PerformanceMetric:
    nome: str
    valores_ms: list[float] = field(default_factory=list)

    @property
    def p50(self) -> float:
        return round(statistics.median(self.valores_ms), 1) if self.valores_ms else 0

    @property
    def p95(self) -> float:
        if not self.valores_ms:
            return 0
        sorted_v = sorted(self.valores_ms)
        idx = int(len(sorted_v) * 0.95)
        return round(sorted_v[min(idx, len(sorted_v) - 1)], 1)

    @property
    def media(self) -> float:
        return round(statistics.mean(self.valores_ms), 1) if self.valores_ms else 0

    @property
    def maximo(self) -> float:
        return round(max(self.valores_ms), 1) if self.valores_ms else 0

    @property
    def minimo(self) -> float:
        return round(min(self.valores_ms), 1) if self.valores_ms else 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _login(client: httpx.AsyncClient, email: str, password: str) -> tuple[str, str]:
    """Login e devolve (token, user_id)."""
    resp = await client.post(
        f"{API_URL}/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["user_id"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _medir(func):
    """Decorador para medir latência de funções async."""
    async def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = await func(*args, **kwargs)
        latencia = (time.perf_counter() - t0) * 1000
        return result, round(latencia, 1)
    return wrapper


# ===========================================================================
# 1. TESTES DE IMPLEMENTAÇÃO
# ===========================================================================

async def testes_implementacao(client: httpx.AsyncClient) -> list[TestResult]:
    resultados = []

    # T-IMP-01: Health Check
    try:
        t0 = time.perf_counter()
        resp = await client.get(f"{BASE_URL}/health", timeout=10)
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        ok = resp.status_code == 200 and data.get("status") == "ok"
        chaves = data.get("chaves", {})
        resultados.append(TestResult(
            id="T-IMP-01", categoria="implementacao", subcategoria="sistema",
            nome="Health Check — API operacional",
            passou=ok, latencia_ms=round(lat, 1),
            detalhes=f"Status: {data.get('status')} | Versão: {data.get('versao')} | Chaves: {json.dumps(chaves)}",
            metricas={"chaves": chaves},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="T-IMP-01", categoria="implementacao", subcategoria="sistema",
            nome="Health Check — API operacional",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # T-IMP-02: Conectividade PostgreSQL
    try:
        t0 = time.perf_counter()
        from app.db.database import get_db, engine
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            pg_version = result.scalar()
            result2 = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            ))
            tabelas = [row[0] for row in result2.fetchall()]
        lat = (time.perf_counter() - t0) * 1000
        tabelas_esperadas = ["artefactos", "consentimentos", "perfis_biograficos",
                             "sessoes", "tokens_reset_password", "utilizadores"]
        todas_presentes = all(t in tabelas for t in tabelas_esperadas)
        resultados.append(TestResult(
            id="T-IMP-02", categoria="implementacao", subcategoria="database",
            nome="Conectividade PostgreSQL + tabelas",
            passou=todas_presentes, latencia_ms=round(lat, 1),
            detalhes=f"PostgreSQL: {pg_version[:30]}... | Tabelas: {tabelas}",
            metricas={"pg_version": pg_version, "tabelas": tabelas, "n_tabelas": len(tabelas)},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="T-IMP-02", categoria="implementacao", subcategoria="database",
            nome="Conectividade PostgreSQL + tabelas",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # T-IMP-03: Conectividade Redis
    try:
        t0 = time.perf_counter()
        from app.services.redis_service import _get_pool
        pool = _get_pool()
        pong = await pool.ping()
        info = await pool.info("server")
        redis_version = info.get("redis_version", "?")
        lat = (time.perf_counter() - t0) * 1000
        resultados.append(TestResult(
            id="T-IMP-03", categoria="implementacao", subcategoria="cache",
            nome="Conectividade Redis + PING",
            passou=bool(pong), latencia_ms=round(lat, 1),
            detalhes=f"Redis {redis_version} | PING={pong}",
            metricas={"redis_version": redis_version},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="T-IMP-03", categoria="implementacao", subcategoria="cache",
            nome="Conectividade Redis + PING",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # T-IMP-04: Chave API Groq válida
    try:
        t0 = time.perf_counter()
        from app.services.groq_service import _get_client
        groq_client = _get_client()
        resp_groq = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Diz apenas: OK"}],
            temperature=0, max_tokens=5,
        )
        resposta = resp_groq.choices[0].message.content.strip()
        lat = (time.perf_counter() - t0) * 1000
        resultados.append(TestResult(
            id="T-IMP-04", categoria="implementacao", subcategoria="ia",
            nome="API Groq (Llama 3.3 70B) — chave válida",
            passou=len(resposta) > 0, latencia_ms=round(lat, 1),
            detalhes=f"Resposta: '{resposta}' | Modelo: {resp_groq.model}",
            metricas={"modelo": resp_groq.model, "tokens_prompt": resp_groq.usage.prompt_tokens,
                       "tokens_resposta": resp_groq.usage.completion_tokens},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="T-IMP-04", categoria="implementacao", subcategoria="ia",
            nome="API Groq (Llama 3.3 70B) — chave válida",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # T-IMP-05: Chave API Gemini válida
    try:
        t0 = time.perf_counter()
        from app.services.gemini_service import _get_client
        from google.genai import types as genai_types
        gemini = _get_client()
        resp_gemini = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents="Responde apenas com JSON: {\"status\": \"ok\"}",
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0, max_output_tokens=20,
            ),
        )
        resposta = (resp_gemini.text or "").strip()
        lat = (time.perf_counter() - t0) * 1000
        resultados.append(TestResult(
            id="T-IMP-05", categoria="implementacao", subcategoria="ia",
            nome="API Gemini 2.5 Flash — chave válida + JSON mode",
            passou='"ok"' in resposta or '"status"' in resposta,
            latencia_ms=round(lat, 1),
            detalhes=f"Resposta: {resposta}",
            metricas={"resposta_json": resposta},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="T-IMP-05", categoria="implementacao", subcategoria="ia",
            nome="API Gemini 2.5 Flash — chave válida + JSON mode",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # T-IMP-06: Edge-TTS funcional (síntese de voz PT-PT)
    try:
        t0 = time.perf_counter()
        from app.services.tts_service import sintetizar
        audio_bytes = await sintetizar("Olá, chamo-me Raquel.", voz="pt-PT-RaquelNeural")
        lat = (time.perf_counter() - t0) * 1000
        tamanho_kb = len(audio_bytes) / 1024
        resultados.append(TestResult(
            id="T-IMP-06", categoria="implementacao", subcategoria="voz",
            nome="Edge-TTS (voz pt-PT-RaquelNeural) — funcional",
            passou=len(audio_bytes) > 1000, latencia_ms=round(lat, 1),
            detalhes=f"Áudio gerado: {tamanho_kb:.1f} KB | Formato: MP3",
            metricas={"tamanho_bytes": len(audio_bytes), "tamanho_kb": round(tamanho_kb, 1)},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="T-IMP-06", categoria="implementacao", subcategoria="voz",
            nome="Edge-TTS (voz pt-PT-RaquelNeural) — funcional",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # T-IMP-07: Utilizadores de seed existem
    try:
        t0 = time.perf_counter()
        from sqlalchemy import select, func
        from app.models.utilizador import Utilizador, PerfilBiografico, Sessao
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            n_users = (await db.execute(select(func.count(Utilizador.id)))).scalar()
            n_perfis = (await db.execute(select(func.count(PerfilBiografico.id)))).scalar()
            n_sessoes = (await db.execute(select(func.count(Sessao.id)))).scalar()
        lat = (time.perf_counter() - t0) * 1000
        resultados.append(TestResult(
            id="T-IMP-07", categoria="implementacao", subcategoria="database",
            nome="Dados de seed — utilizadores, perfis, sessões",
            passou=n_users >= 3, latencia_ms=round(lat, 1),
            detalhes=f"Utilizadores: {n_users} | Perfis: {n_perfis} | Sessões: {n_sessoes}",
            metricas={"utilizadores": n_users, "perfis": n_perfis, "sessoes": n_sessoes},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="T-IMP-07", categoria="implementacao", subcategoria="database",
            nome="Dados de seed — utilizadores, perfis, sessões",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    return resultados


# ===========================================================================
# 2. TESTES FUNCIONAIS
# ===========================================================================

async def testes_funcionais(client: httpx.AsyncClient) -> list[TestResult]:
    resultados = []

    # ── AUTH ─────────────────────────────────────────────────────────────

    # TF-AUTH-01: Login correto
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/auth/login",
            data={"username": TEST_EMAIL_IDOSO, "password": TEST_PASS_IDOSO},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        ok = resp.status_code == 200 and "access_token" in data and "user_id" in data
        resultados.append(TestResult(
            id="TF-AUTH-01", categoria="funcional", subcategoria="auth",
            nome="Login com credenciais válidas — JWT emitido",
            passou=ok, latencia_ms=round(lat, 1),
            detalhes=f"HTTP {resp.status_code} | user_id={data.get('user_id', '?')[:8]}... | role={data.get('role')}",
            metricas={"status": resp.status_code, "role": data.get("role")},
        ))
        token = data.get("access_token", "")
        user_id = data.get("user_id", "")
        refresh_token = data.get("refresh_token", "")
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-AUTH-01", categoria="funcional", subcategoria="auth",
            nome="Login com credenciais válidas — JWT emitido",
            passou=False, detalhes=f"Erro: {exc}",
        ))
        return resultados  # Sem token, testes seguintes falhariam

    headers = _auth_headers(token)

    # TF-AUTH-02: Login com password errada → 401
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/auth/login",
            data={"username": TEST_EMAIL_IDOSO, "password": "PasswordErrada123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        lat = (time.perf_counter() - t0) * 1000
        resultados.append(TestResult(
            id="TF-AUTH-02", categoria="funcional", subcategoria="auth",
            nome="Login com password errada — rejeição 401",
            passou=resp.status_code == 401, latencia_ms=round(lat, 1),
            detalhes=f"HTTP {resp.status_code} (esperado 401)",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-AUTH-02", categoria="funcional", subcategoria="auth",
            nome="Login com password errada — rejeição 401",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-AUTH-03: GET /me com token válido
    try:
        t0 = time.perf_counter()
        resp = await client.get(f"{API_URL}/auth/me", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        resultados.append(TestResult(
            id="TF-AUTH-03", categoria="funcional", subcategoria="auth",
            nome="GET /me — dados do utilizador autenticado",
            passou=resp.status_code == 200 and data.get("email") == TEST_EMAIL_IDOSO,
            latencia_ms=round(lat, 1),
            detalhes=f"Email: {data.get('email')} | Nome: {data.get('nome')} | Onboarding: {data.get('onboarding_completo')}",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-AUTH-03", categoria="funcional", subcategoria="auth",
            nome="GET /me — dados do utilizador autenticado",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-AUTH-04: GET /me sem token → 401
    try:
        t0 = time.perf_counter()
        resp = await client.get(f"{API_URL}/auth/me")
        lat = (time.perf_counter() - t0) * 1000
        resultados.append(TestResult(
            id="TF-AUTH-04", categoria="funcional", subcategoria="auth",
            nome="GET /me sem token — rejeição 401",
            passou=resp.status_code in (401, 403), latencia_ms=round(lat, 1),
            detalhes=f"HTTP {resp.status_code} (esperado 401/403)",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-AUTH-04", categoria="funcional", subcategoria="auth",
            nome="GET /me sem token — rejeição 401",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-AUTH-05: Refresh token
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        resultados.append(TestResult(
            id="TF-AUTH-05", categoria="funcional", subcategoria="auth",
            nome="Refresh token — novo par de tokens emitido",
            passou=resp.status_code == 200 and "access_token" in data,
            latencia_ms=round(lat, 1),
            detalhes=f"HTTP {resp.status_code} | Novo token emitido: {'sim' if 'access_token' in data else 'não'}",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-AUTH-05", categoria="funcional", subcategoria="auth",
            nome="Refresh token — novo par de tokens emitido",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-AUTH-06: GET /perfil — perfil biográfico
    try:
        t0 = time.perf_counter()
        resp = await client.get(f"{API_URL}/auth/perfil", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        tem_perfil = data.get("perfil_json") is not None
        campos = list(data.get("perfil_json", {}).keys()) if tem_perfil else []
        resultados.append(TestResult(
            id="TF-AUTH-06", categoria="funcional", subcategoria="auth",
            nome="GET /perfil — perfil biográfico do utilizador",
            passou=resp.status_code == 200 and tem_perfil,
            latencia_ms=round(lat, 1),
            detalhes=f"Perfil presente: {tem_perfil} | Campos: {len(campos)} | Temas: {data.get('temas_explorados', [])}",
            metricas={"campos_perfil": campos, "n_campos": len(campos)},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-AUTH-06", categoria="funcional", subcategoria="auth",
            nome="GET /perfil — perfil biográfico do utilizador",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # ── CHAT PERSONALIZADO ───────────────────────────────────────────────

    # TF-CHAT-01: Conversa personalizada — resposta com perfil
    session_id = None
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/chat/conversa/personalizada",
            headers=headers,
            json={"user_id": user_id, "mensagem": "Olá, bom dia!", "tema": "memorias",
                  "session_id": None, "historico": None},
            timeout=30,
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        session_id = data.get("session_id")
        resposta = data.get("resposta", "")
        resultados.append(TestResult(
            id="TF-CHAT-01", categoria="funcional", subcategoria="chat",
            nome="Conversa personalizada — resposta com perfil biográfico",
            passou=resp.status_code == 200 and len(resposta) > 10,
            latencia_ms=round(lat, 1),
            detalhes=f"Resposta ({len(resposta)} chars): '{resposta[:80]}...' | TTFT: {data.get('ttft_ms')}ms | Tema: {data.get('tema')}",
            metricas={"ttft_ms": data.get("ttft_ms"), "chars_resposta": len(resposta),
                       "session_id": session_id},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-CHAT-01", categoria="funcional", subcategoria="chat",
            nome="Conversa personalizada — resposta com perfil biográfico",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-CHAT-02: Continuidade da sessão (segunda mensagem)
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/chat/conversa/personalizada",
            headers=headers,
            json={"user_id": user_id, "mensagem": "Lembro-me de quando era pequeno em Évora.",
                  "tema": "memorias", "session_id": session_id, "historico": None},
            timeout=30,
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        resposta = data.get("resposta", "")
        resultados.append(TestResult(
            id="TF-CHAT-02", categoria="funcional", subcategoria="chat",
            nome="Continuidade de sessão — 2ª mensagem com contexto Redis",
            passou=resp.status_code == 200 and len(resposta) > 10,
            latencia_ms=round(lat, 1),
            detalhes=f"Resposta: '{resposta[:80]}...' | Session mantida: {data.get('session_id') == session_id}",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-CHAT-02", categoria="funcional", subcategoria="chat",
            nome="Continuidade de sessão — 2ª mensagem com contexto Redis",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-CHAT-03: Todos os 6 temas respondem
    temas = ["memorias", "familia", "saude", "entretenimento", "exercicio", "geral"]
    for tema in temas:
        try:
            t0 = time.perf_counter()
            resp = await client.post(
                f"{API_URL}/chat/conversa/personalizada",
                headers=headers,
                json={"user_id": user_id, "mensagem": "Olá", "tema": tema,
                      "session_id": None, "historico": None, "registar_tema": False},
                timeout=30,
            )
            lat = (time.perf_counter() - t0) * 1000
            data = resp.json()
            resultados.append(TestResult(
                id=f"TF-CHAT-03-{tema}", categoria="funcional", subcategoria="chat",
                nome=f"Tema '{tema}' — resposta válida",
                passou=resp.status_code == 200 and len(data.get("resposta", "")) > 5,
                latencia_ms=round(lat, 1),
                detalhes=f"HTTP {resp.status_code} | Resposta: {len(data.get('resposta', ''))} chars | TTFT: {data.get('ttft_ms')}ms",
                metricas={"ttft_ms": data.get("ttft_ms")},
            ))
        except Exception as exc:
            resultados.append(TestResult(
                id=f"TF-CHAT-03-{tema}", categoria="funcional", subcategoria="chat",
                nome=f"Tema '{tema}' — resposta válida",
                passou=False, detalhes=f"Erro: {exc}",
            ))
        await asyncio.sleep(1)  # Evitar rate limit

    # ── MEMÓRIA CURTA (Redis) ─────────────────────────────────────────────

    # TF-MEM-01: Escrita e leitura no Redis
    try:
        from app.services.redis_service import set_historico, get_historico, delete_historico
        test_session = f"test-{uuid.uuid4()}"
        historico_test = [
            {"role": "user", "content": "Olá"},
            {"role": "assistant", "content": "Olá, como está?"},
        ]
        t0 = time.perf_counter()
        await set_historico(test_session, historico_test)
        recuperado = await get_historico(test_session)
        lat = (time.perf_counter() - t0) * 1000
        ok = len(recuperado) == 2 and recuperado[0]["content"] == "Olá"
        await delete_historico(test_session)
        resultados.append(TestResult(
            id="TF-MEM-01", categoria="funcional", subcategoria="memoria_curta",
            nome="Redis — escrita + leitura + eliminação de histórico",
            passou=ok, latencia_ms=round(lat, 1),
            detalhes=f"Escrito: 2 msgs | Lido: {len(recuperado)} msgs | Conteúdo correto: {ok}",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-MEM-01", categoria="funcional", subcategoria="memoria_curta",
            nome="Redis — escrita + leitura + eliminação de histórico",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-MEM-02: append_interacao
    try:
        from app.services.redis_service import append_interacao, get_historico, delete_historico
        test_session = f"test-{uuid.uuid4()}"
        t0 = time.perf_counter()
        hist = await append_interacao(test_session, "Pergunta", "Resposta")
        hist = await append_interacao(test_session, "Pergunta 2", "Resposta 2")
        lat = (time.perf_counter() - t0) * 1000
        ok = len(hist) == 4
        await delete_historico(test_session)
        resultados.append(TestResult(
            id="TF-MEM-02", categoria="funcional", subcategoria="memoria_curta",
            nome="Redis — append_interacao (acumula pares user/assistant)",
            passou=ok, latencia_ms=round(lat, 1),
            detalhes=f"2 appends → {len(hist)} mensagens (esperado: 4)",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-MEM-02", categoria="funcional", subcategoria="memoria_curta",
            nome="Redis — append_interacao (acumula pares user/assistant)",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # ── MEMÓRIA LONGA (Extração Gemini + Merge LangGraph) ─────────────────

    # TF-MEM-L-01: Extração de perfil via Gemini
    try:
        from app.services.gemini_service import extrair_perfil
        historico_teste = [
            {"role": "assistant", "content": "Como se chama?"},
            {"role": "user", "content": "Chamo-me Joaquim Ferreira, nasci em Viseu."},
            {"role": "assistant", "content": "Que idade tem?"},
            {"role": "user", "content": "Tenho 78 anos, sou reformado, fui padeiro."},
        ]
        t0 = time.perf_counter()
        perfil = await extrair_perfil(historico_teste)
        lat = (time.perf_counter() - t0) * 1000
        campos_preenchidos = [k for k, v in perfil.items()
                              if v is not None and v != [] and v != {}]
        resultados.append(TestResult(
            id="TF-MEM-L-01", categoria="funcional", subcategoria="memoria_longa",
            nome="Gemini — extração de perfil biográfico (JSON estruturado)",
            passou=len(campos_preenchidos) >= 3 and perfil.get("nome") is not None,
            latencia_ms=round(lat, 1),
            detalhes=f"Nome: {perfil.get('nome')} | Campos preenchidos: {campos_preenchidos}",
            metricas={"campos_preenchidos": campos_preenchidos, "n_campos": len(campos_preenchidos)},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-MEM-L-01", categoria="funcional", subcategoria="memoria_longa",
            nome="Gemini — extração de perfil biográfico (JSON estruturado)",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-MEM-L-02: Merge de perfis via LangGraph
    try:
        from app.services.langgraph_service import executar_merge
        perfil_antigo = {"nome": "Joaquim", "terra_natal": "Viseu", "profissao": "Padeiro"}
        novos_factos = json.dumps({"familia": "Casado com a Maria, 3 filhos", "locais": ["Viseu", "Lisboa"]})
        t0 = time.perf_counter()
        fundido = await executar_merge(
            user_id=f"test-{uuid.uuid4()}",
            perfil_antigo=perfil_antigo,
            resumo_sessao=novos_factos,
        )
        lat = (time.perf_counter() - t0) * 1000
        preservou_nome = fundido.get("nome") == "Joaquim"
        adicionou_familia = fundido.get("familia") is not None
        resultados.append(TestResult(
            id="TF-MEM-L-02", categoria="funcional", subcategoria="memoria_longa",
            nome="LangGraph + Gemini/Groq — merge de perfis sem perda de dados",
            passou=preservou_nome and adicionou_familia,
            latencia_ms=round(lat, 1),
            detalhes=f"Nome preservado: {preservou_nome} | Família adicionada: {adicionou_familia} | Campos: {list(fundido.keys())}",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-MEM-L-02", categoria="funcional", subcategoria="memoria_longa",
            nome="LangGraph + Gemini/Groq — merge de perfis sem perda de dados",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-MEM-L-03: Resumo narrativo via Gemini
    try:
        from app.services.gemini_service import gerar_resumo_narrativo
        historico_teste = [
            {"role": "user", "content": "Lembro-me que aos 12 anos fui pela primeira vez ao mar, em Figueira da Foz. O meu pai levou-me e eu fiquei maravilhado com a imensidão da água."},
        ]
        t0 = time.perf_counter()
        resumo = await gerar_resumo_narrativo(historico_teste)
        lat = (time.perf_counter() - t0) * 1000
        resultados.append(TestResult(
            id="TF-MEM-L-03", categoria="funcional", subcategoria="memoria_longa",
            nome="Gemini — geração de resumo narrativo biográfico",
            passou=len(resumo) > 50,
            latencia_ms=round(lat, 1),
            detalhes=f"Resumo ({len(resumo)} chars): '{resumo[:100]}...'",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-MEM-L-03", categoria="funcional", subcategoria="memoria_longa",
            nome="Gemini — geração de resumo narrativo biográfico",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # ── ENCERRAR SESSÃO (pipeline completo) ──────────────────────────────

    # TF-ENC-01: Encerrar sessão com merge e persistência
    try:
        historico_sessao = [
            {"role": "assistant", "content": "Lembra-se de algum momento especial da sua infância?"},
            {"role": "user", "content": "Sim, lembro-me de ir ao rio com o meu avô. Ele ensinou-me a pescar quando eu tinha uns 8 anos."},
            {"role": "assistant", "content": "Que memória bonita! E o seu avô, como era?"},
            {"role": "user", "content": "Era um homem alto e forte, com mãos grandes. Chamava-se Augusto."},
        ]
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/chat/sessao/encerrar",
            headers=headers,
            json={"user_id": user_id, "tema": "memorias",
                  "session_id": session_id, "historico_sessao": historico_sessao},
            timeout=60,
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        resultados.append(TestResult(
            id="TF-ENC-01", categoria="funcional", subcategoria="encerramento",
            nome="Encerrar sessão — extração + merge + persistência completa",
            passou=resp.status_code == 200 and data.get("perfil_atualizado", False),
            latencia_ms=round(lat, 1),
            detalhes=f"Perfil atualizado: {data.get('perfil_atualizado')} | Msg: {data.get('mensagem')} | Erro: {data.get('erro')}",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-ENC-01", categoria="funcional", subcategoria="encerramento",
            nome="Encerrar sessão — extração + merge + persistência completa",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # ── ARTEFACTOS ────────────────────────────────────────────────────────

    # TF-ART-01: Gerar Timeline HTML
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/artefactos/timeline",
            headers=headers,
            json={"user_id": user_id},
            timeout=30,
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        resultados.append(TestResult(
            id="TF-ART-01", categoria="funcional", subcategoria="artefactos",
            nome="Gerar Timeline HTML — artefacto standalone",
            passou=resp.status_code == 200 and data.get("tipo") == "timeline_html",
            latencia_ms=round(lat, 1),
            detalhes=f"Tipo: {data.get('tipo')} | URL: {data.get('url_download')} | Gerado: {data.get('gerado_em')}",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-ART-01", categoria="funcional", subcategoria="artefactos",
            nome="Gerar Timeline HTML — artefacto standalone",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-ART-02: Gerar Livro PDF
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/artefactos/livro-memorias",
            headers=headers,
            json={"user_id": user_id},
            timeout=120,
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        resultados.append(TestResult(
            id="TF-ART-02", categoria="funcional", subcategoria="artefactos",
            nome="Gerar Livro de Memórias PDF — capítulos narrativos Gemini",
            passou=resp.status_code == 200 and data.get("tipo") == "livro_pdf",
            latencia_ms=round(lat, 1),
            detalhes=f"Tipo: {data.get('tipo')} | Gerado em: {lat/1000:.1f}s",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-ART-02", categoria="funcional", subcategoria="artefactos",
            nome="Gerar Livro de Memórias PDF — capítulos narrativos Gemini",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-ART-03: Gerar Cartões PDF
    try:
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/artefactos/cartoes",
            headers=headers,
            json={"user_id": user_id},
            timeout=120,
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        resultados.append(TestResult(
            id="TF-ART-03", categoria="funcional", subcategoria="artefactos",
            nome="Gerar Cartões de Histórias PDF — story cards",
            passou=resp.status_code == 200 and data.get("tipo") == "cartoes_pdf",
            latencia_ms=round(lat, 1),
            detalhes=f"Tipo: {data.get('tipo')} | Gerado em: {lat/1000:.1f}s",
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-ART-03", categoria="funcional", subcategoria="artefactos",
            nome="Gerar Cartões de Histórias PDF — story cards",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    # TF-ART-04: Listar artefactos
    try:
        t0 = time.perf_counter()
        resp = await client.get(
            f"{API_URL}/artefactos/?user_id={user_id}",
            headers=headers,
        )
        lat = (time.perf_counter() - t0) * 1000
        data = resp.json()
        n = len(data.get("artefactos", []))
        resultados.append(TestResult(
            id="TF-ART-04", categoria="funcional", subcategoria="artefactos",
            nome="Listar artefactos do utilizador",
            passou=resp.status_code == 200 and n >= 1,
            latencia_ms=round(lat, 1),
            detalhes=f"Artefactos encontrados: {n}",
            metricas={"n_artefactos": n},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TF-ART-04", categoria="funcional", subcategoria="artefactos",
            nome="Listar artefactos do utilizador",
            passou=False, detalhes=f"Erro: {exc}",
        ))

    return resultados


# ===========================================================================
# 3. TESTES DE DESEMPENHO
# ===========================================================================

async def testes_desempenho(client: httpx.AsyncClient) -> tuple[list[TestResult], dict]:
    """Mede latências com múltiplas iterações para obter P50, P95, etc."""
    resultados = []
    metricas_perf: dict[str, Any] = {}

    token, user_id = await _login(client, TEST_EMAIL_IDOSO, TEST_PASS_IDOSO)
    headers = _auth_headers(token)

    N_ITER = 5  # Iterações para cada medição

    # ── TD-01: Latência Health Check ─────────────────────────────────────
    pm = PerformanceMetric(nome="Health Check")
    for _ in range(N_ITER):
        t0 = time.perf_counter()
        await client.get(f"{BASE_URL}/health")
        pm.valores_ms.append((time.perf_counter() - t0) * 1000)
    metricas_perf["health_check"] = asdict_perf(pm)
    resultados.append(TestResult(
        id="TD-01", categoria="desempenho", subcategoria="latencia",
        nome=f"Health Check — {N_ITER} iterações",
        passou=pm.p95 < 200,
        detalhes=f"P50={pm.p50}ms | P95={pm.p95}ms | Max={pm.maximo}ms | Min={pm.minimo}ms",
        metricas=asdict_perf(pm),
    ))

    # ── TD-02: Latência Login ────────────────────────────────────────────
    pm = PerformanceMetric(nome="Login (bcrypt)")
    for _ in range(N_ITER):
        t0 = time.perf_counter()
        await client.post(
            f"{API_URL}/auth/login",
            data={"username": TEST_EMAIL_IDOSO, "password": TEST_PASS_IDOSO},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        pm.valores_ms.append((time.perf_counter() - t0) * 1000)
    metricas_perf["login"] = asdict_perf(pm)
    resultados.append(TestResult(
        id="TD-02", categoria="desempenho", subcategoria="latencia",
        nome=f"Login (bcrypt hash) — {N_ITER} iterações",
        passou=pm.p95 < 1000,
        detalhes=f"P50={pm.p50}ms | P95={pm.p95}ms | Max={pm.maximo}ms",
        metricas=asdict_perf(pm),
    ))

    # ── TD-03: Latência GET /me ──────────────────────────────────────────
    pm = PerformanceMetric(nome="GET /me")
    for _ in range(N_ITER):
        t0 = time.perf_counter()
        await client.get(f"{API_URL}/auth/me", headers=headers)
        pm.valores_ms.append((time.perf_counter() - t0) * 1000)
    metricas_perf["get_me"] = asdict_perf(pm)
    resultados.append(TestResult(
        id="TD-03", categoria="desempenho", subcategoria="latencia",
        nome=f"GET /me (decode JWT + DB) — {N_ITER} iterações",
        passou=pm.p95 < 200,
        detalhes=f"P50={pm.p50}ms | P95={pm.p95}ms | Max={pm.maximo}ms",
        metricas=asdict_perf(pm),
    ))

    # ── TD-04: Latência Chat Personalizado (LLM) ────────────────────────
    pm = PerformanceMetric(nome="Chat Personalizado (Groq)")
    ttfts = []
    for i in range(3):  # Menos iterações (API calls custosas)
        t0 = time.perf_counter()
        resp = await client.post(
            f"{API_URL}/chat/conversa/personalizada",
            headers=headers,
            json={"user_id": user_id, "mensagem": f"Olá, teste {i+1}",
                  "tema": "geral", "session_id": None, "historico": None,
                  "registar_tema": False},
            timeout=30,
        )
        pm.valores_ms.append((time.perf_counter() - t0) * 1000)
        data = resp.json()
        if data.get("ttft_ms"):
            ttfts.append(data["ttft_ms"])
        await asyncio.sleep(1)

    metricas_perf["chat_personalizado"] = asdict_perf(pm)
    metricas_perf["chat_personalizado"]["ttft_medio"] = round(statistics.mean(ttfts), 1) if ttfts else None
    resultados.append(TestResult(
        id="TD-04", categoria="desempenho", subcategoria="latencia",
        nome=f"Chat personalizado Groq (Llama 3.3 70B) — {len(pm.valores_ms)} iterações",
        passou=pm.p95 < 5000,
        detalhes=f"Latência total: P50={pm.p50}ms P95={pm.p95}ms | TTFT médio Groq: {metricas_perf['chat_personalizado']['ttft_medio']}ms",
        metricas=metricas_perf["chat_personalizado"],
    ))

    # ── TD-05: Latência Redis (operações internas) ───────────────────────
    try:
        from app.services.redis_service import set_historico, get_historico, delete_historico

        pm_write = PerformanceMetric(nome="Redis SETEX")
        pm_read = PerformanceMetric(nome="Redis GET")
        pm_del = PerformanceMetric(nome="Redis DEL")

        historico_10 = [{"role": "user" if i % 2 == 0 else "assistant",
                         "content": f"Mensagem de teste número {i}"} for i in range(10)]

        for _ in range(N_ITER * 2):
            sid = f"perf-{uuid.uuid4()}"

            t0 = time.perf_counter()
            await set_historico(sid, historico_10)
            pm_write.valores_ms.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            await get_historico(sid)
            pm_read.valores_ms.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            await delete_historico(sid)
            pm_del.valores_ms.append((time.perf_counter() - t0) * 1000)

        metricas_perf["redis_write"] = asdict_perf(pm_write)
        metricas_perf["redis_read"] = asdict_perf(pm_read)
        metricas_perf["redis_delete"] = asdict_perf(pm_del)
        resultados.append(TestResult(
            id="TD-05", categoria="desempenho", subcategoria="redis",
            nome=f"Redis — SETEX/GET/DEL (10 msgs, {N_ITER*2} iterações)",
            passou=pm_read.p95 < 10,
            detalhes=f"WRITE P50={pm_write.p50}ms | READ P50={pm_read.p50}ms | DEL P50={pm_del.p50}ms",
            metricas={"write": asdict_perf(pm_write), "read": asdict_perf(pm_read), "delete": asdict_perf(pm_del)},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TD-05", categoria="desempenho", subcategoria="redis",
            nome="Redis — SETEX/GET/DEL", passou=False, detalhes=f"Erro: {exc}",
        ))

    # ── TD-06: Latência PostgreSQL (queries internas) ────────────────────
    try:
        from sqlalchemy import select, text
        from app.models.utilizador import Utilizador, PerfilBiografico, Sessao
        from app.db.database import AsyncSessionLocal

        pm_user = PerformanceMetric(nome="SELECT utilizador")
        pm_perfil = PerformanceMetric(nome="SELECT perfil")
        pm_sessoes = PerformanceMetric(nome="SELECT sessões")

        async with AsyncSessionLocal() as db:
            for _ in range(N_ITER * 2):
                t0 = time.perf_counter()
                await db.execute(select(Utilizador).where(Utilizador.email == TEST_EMAIL_IDOSO))
                pm_user.valores_ms.append((time.perf_counter() - t0) * 1000)

                t0 = time.perf_counter()
                await db.execute(
                    select(PerfilBiografico).where(
                        PerfilBiografico.utilizador_id == uuid.UUID(user_id)))
                pm_perfil.valores_ms.append((time.perf_counter() - t0) * 1000)

                t0 = time.perf_counter()
                await db.execute(
                    select(Sessao).where(
                        Sessao.utilizador_id == uuid.UUID(user_id)).order_by(Sessao.criada_em))
                pm_sessoes.valores_ms.append((time.perf_counter() - t0) * 1000)

        metricas_perf["pg_user"] = asdict_perf(pm_user)
        metricas_perf["pg_perfil"] = asdict_perf(pm_perfil)
        metricas_perf["pg_sessoes"] = asdict_perf(pm_sessoes)
        resultados.append(TestResult(
            id="TD-06", categoria="desempenho", subcategoria="postgresql",
            nome=f"PostgreSQL — SELECT utilizador/perfil/sessões ({N_ITER*2} iterações)",
            passou=pm_user.p95 < 50,
            detalhes=f"User P50={pm_user.p50}ms | Perfil P50={pm_perfil.p50}ms | Sessões P50={pm_sessoes.p50}ms",
            metricas={"user": asdict_perf(pm_user), "perfil": asdict_perf(pm_perfil), "sessoes": asdict_perf(pm_sessoes)},
        ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TD-06", categoria="desempenho", subcategoria="postgresql",
            nome="PostgreSQL — SELECT queries", passou=False, detalhes=f"Erro: {exc}",
        ))

    # ── TD-07: Latência TTS Edge-TTS ─────────────────────────────────────
    try:
        from app.services.tts_service import sintetizar

        textos = [
            ("curto", "Olá, como está?"),
            ("medio", "Lembro-me muito bem desses tempos. O meu avô era um homem forte e trabalhador que nos ensinava o valor da terra."),
            ("longo", "A minha infância foi passada em Viseu, numa casa antiga junto ao rio. " * 5),
        ]

        for label, texto in textos:
            pm = PerformanceMetric(nome=f"TTS {label}")
            tamanhos = []
            for _ in range(2):
                t0 = time.perf_counter()
                audio = await sintetizar(texto)
                pm.valores_ms.append((time.perf_counter() - t0) * 1000)
                tamanhos.append(len(audio))

            metricas_perf[f"tts_{label}"] = {
                **asdict_perf(pm),
                "tamanho_medio_kb": round(statistics.mean(tamanhos) / 1024, 1),
                "n_palavras": len(texto.split()),
            }
            resultados.append(TestResult(
                id=f"TD-07-{label}", categoria="desempenho", subcategoria="tts",
                nome=f"TTS Edge-TTS — texto {label} ({len(texto.split())} palavras)",
                passou=pm.p95 < 15000,
                detalhes=f"P50={pm.p50}ms | Áudio={round(statistics.mean(tamanhos)/1024, 1)} KB",
                metricas=metricas_perf[f"tts_{label}"],
            ))
    except Exception as exc:
        resultados.append(TestResult(
            id="TD-07", categoria="desempenho", subcategoria="tts",
            nome="TTS Edge-TTS", passou=False, detalhes=f"Erro: {exc}",
        ))

    # ── TD-08: Latência Geração Timeline (rápido, sem IA) ────────────────
    pm = PerformanceMetric(nome="Timeline HTML")
    for _ in range(3):
        t0 = time.perf_counter()
        await client.post(
            f"{API_URL}/artefactos/timeline",
            headers=headers,
            json={"user_id": user_id},
            timeout=30,
        )
        pm.valores_ms.append((time.perf_counter() - t0) * 1000)
    metricas_perf["timeline"] = asdict_perf(pm)
    resultados.append(TestResult(
        id="TD-08", categoria="desempenho", subcategoria="artefactos",
        nome=f"Geração Timeline HTML — {len(pm.valores_ms)} iterações",
        passou=pm.p95 < 2000,
        detalhes=f"P50={pm.p50}ms | P95={pm.p95}ms | Max={pm.maximo}ms",
        metricas=asdict_perf(pm),
    ))

    return resultados, metricas_perf


def asdict_perf(pm: PerformanceMetric) -> dict:
    return {
        "nome": pm.nome,
        "p50_ms": pm.p50,
        "p95_ms": pm.p95,
        "media_ms": pm.media,
        "max_ms": pm.maximo,
        "min_ms": pm.minimo,
        "n_amostras": len(pm.valores_ms),
        "valores": [round(v, 1) for v in pm.valores_ms],
    }


# ===========================================================================
# RELATÓRIO FORMATADO
# ===========================================================================

def imprimir_relatorio(todos: list[TestResult], metricas_perf: dict):
    sep = "═" * 72
    print(f"\n{sep}")
    print("  RELATÓRIO DE TESTES — MEMÓRIAS VIVAS")
    print(f"  Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(sep)

    categorias = {}
    for r in todos:
        categorias.setdefault(r.categoria, []).append(r)

    total_ok = sum(1 for r in todos if r.passou)
    total = len(todos)

    for cat_nome, cat_label in [("implementacao", "TESTES DE IMPLEMENTAÇÃO"),
                                 ("funcional", "TESTES FUNCIONAIS"),
                                 ("desempenho", "TESTES DE DESEMPENHO")]:
        testes = categorias.get(cat_nome, [])
        if not testes:
            continue

        ok = sum(1 for t in testes if t.passou)
        print(f"\n{'─' * 72}")
        print(f"  {cat_label} — {ok}/{len(testes)} passaram")
        print(f"{'─' * 72}")

        for t in testes:
            status = "✅" if t.passou else "❌"
            lat_str = f" [{t.latencia_ms:.0f}ms]" if t.latencia_ms else ""
            print(f"  {status} {t.id}: {t.nome}{lat_str}")
            if t.detalhes:
                # Truncar detalhes longos
                d = t.detalhes if len(t.detalhes) < 120 else t.detalhes[:117] + "..."
                print(f"     → {d}")

    # Tabela de desempenho
    if metricas_perf:
        print(f"\n{'─' * 72}")
        print("  TABELA DE DESEMPENHO — LATÊNCIAS MEDIDAS")
        print(f"{'─' * 72}")
        print(f"  {'Componente':<35} {'P50':>8} {'P95':>8} {'Max':>8} {'N':>4}")
        print(f"  {'─'*35} {'─'*8} {'─'*8} {'─'*8} {'─'*4}")
        for key, val in metricas_perf.items():
            if isinstance(val, dict) and "p50_ms" in val:
                nome = val.get("nome", key)[:35]
                print(f"  {nome:<35} {val['p50_ms']:>7.1f}ms {val['p95_ms']:>7.1f}ms {val['max_ms']:>7.1f}ms {val['n_amostras']:>4}")

    print(f"\n{sep}")
    print(f"  RESULTADO GLOBAL: {total_ok}/{total} testes passaram ({total_ok/total*100:.0f}%)")
    print(sep)


# ===========================================================================
# MAIN
# ===========================================================================

async def main(args):
    # Inicializar serviços (necessário para testes diretos)
    try:
        from app.services.redis_service import init_redis
        await init_redis()
    except Exception:
        pass

    todos: list[TestResult] = []
    metricas_perf = {}

    async with httpx.AsyncClient(timeout=120) as client:
        if not args.categoria or args.categoria == "implementacao":
            logger.info("=== TESTES DE IMPLEMENTAÇÃO ===")
            todos.extend(await testes_implementacao(client))

        if not args.categoria or args.categoria == "funcional":
            logger.info("=== TESTES FUNCIONAIS ===")
            todos.extend(await testes_funcionais(client))

        if not args.categoria or args.categoria == "desempenho":
            logger.info("=== TESTES DE DESEMPENHO ===")
            res_desemp, metricas_perf = await testes_desempenho(client)
            todos.extend(res_desemp)

    # Imprimir relatório formatado
    imprimir_relatorio(todos, metricas_perf)

    # Guardar JSON completo
    relatorio = {
        "data": datetime.now(timezone.utc).isoformat(),
        "total_testes": len(todos),
        "passaram": sum(1 for r in todos if r.passou),
        "falharam": sum(1 for r in todos if not r.passou),
        "testes": [asdict(r) for r in todos],
        "metricas_desempenho": metricas_perf,
    }

    output_path = Path("/app/relatorio_testes.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Relatório JSON guardado em: %s", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Suite de testes para relatório")
    parser.add_argument(
        "--categoria",
        choices=["implementacao", "funcional", "desempenho"],
        default=None,
        help="Correr apenas uma categoria de testes",
    )
    asyncio.run(main(parser.parse_args()))
