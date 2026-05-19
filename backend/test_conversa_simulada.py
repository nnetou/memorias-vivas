"""
test_conversa_simulada.py — Suite de testes automatizada do pipeline conversacional.

Cobre:
  1. Onboarding — simula um novo utilizador a passar pelo onboarding completo
  2. Dashboard — 5 trocas por cada um dos 6 temas disponíveis

Uso:
    docker exec memorias_vivas_api python test_conversa_simulada.py
    docker exec memorias_vivas_api python test_conversa_simulada.py --onboarding
    docker exec memorias_vivas_api python test_conversa_simulada.py --tema familia
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field

import httpx
from groq import Groq

BASE_URL          = "http://localhost:8000/api/v1"
TEST_EMAIL        = "manuel@memoriasvivas.pt"
TEST_PASS         = "Manuel123"
TROCAS_ONBOARDING = 12
TROCAS_POR_TEMA   = 5
MODEL_RAPIDO      = "llama-3.1-8b-instant"
MODEL_ANALISE     = "llama-3.3-70b-versatile"

TEMAS = [
    ("memorias",       "Memorias"),
    ("familia",        "Familia"),
    ("saude",          "Bem-estar"),
    ("entretenimento", "Entretenimento"),
    ("exercicio",      "Exercicio"),
    ("geral",          "Conversa livre"),
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)
groq_client = Groq()

PERSONAS = {
    "onboarding": (
        "Estás a interagir com um assistente de voz pela primeira vez. "
        "Chamas-te António Ferreira, tens 72 anos, és de Coimbra, reformado, "
        "ex-professor primário, casado com a Conceição, dois filhos (Pedro e Margarida), "
        "três netos. Memória marcante: nascimento do Pedro. "
        "Respondes com frases curtas como se estivesses a falar, às vezes hesitas, "
        "usas expressões portuguesas (pois é, ora bem, olhe que). "
        "Nunca uses linguagem formal nem emojis. "
        "Responde à pergunta feita — não inventes informação não pedida. "
        "Devolve APENAS a tua resposta."
    ),
    "dashboard": (
        "Estás a conversar com a Raquel, uma assistente de voz. "
        "Chamas-te António Ferreira, 72 anos, de Coimbra, ex-professor reformado, "
        "casado com a Conceição, dois filhos, três netos. "
        "Respondes com frases curtas, linguagem falada, às vezes desvias ligeiramente "
        "do tema, expressões como pois, olhe, é verdade, lembro-me de. "
        "Nunca uses linguagem formal nem emojis. Sê genuíno. "
        "Devolve APENAS a tua resposta."
    ),
}

@dataclass
class Troca:
    turno: int
    assistente: str
    utilizador: str
    latencia_ms: float = 0.0

@dataclass
class ResultadoSeccao:
    nome: str
    trocas: list[Troca] = field(default_factory=list)
    relatorio: str = ""
    nota: float = 0.0

def simular_resposta(historico: list[dict], persona: str) -> str:
    resp = groq_client.chat.completions.create(
        model=MODEL_RAPIDO,
        messages=[{"role": "system", "content": PERSONAS[persona]}] + historico,
        temperature=0.85,
        max_tokens=120,
    )
    return resp.choices[0].message.content.strip()

async def login(client: httpx.AsyncClient) -> tuple[str, str]:
    resp = await client.post(
        f"{BASE_URL}/auth/login",
        data={"username": TEST_EMAIL, "password": TEST_PASS},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    me = await client.get(f"{BASE_URL}/auth/me",
                          headers={"Authorization": f"Bearer {token}"})
    me.raise_for_status()
    user_id = me.json().get("id")
    logger.info("Login: %s (%s...)", TEST_EMAIL, user_id[:8])
    return token, user_id

async def testar_onboarding(client, token, user_id) -> ResultadoSeccao:
    logger.info("\n--- ONBOARDING (%d turnos max) ---", TROCAS_ONBOARDING)
    headers   = {"Authorization": f"Bearer {token}"}
    historico = []
    hist_sim  = []
    trocas    = []

    for turno in range(1, TROCAS_ONBOARDING + 1):
        msg_user = "" if turno == 1 else simular_resposta(hist_sim, "onboarding")
        if msg_user:
            logger.info("T%02d Antonio: %s", turno, msg_user[:70])

        t0 = time.perf_counter()
        try:
            resp = await client.post(
                f"{BASE_URL}/chat/onboarding",
                headers=headers,
                json={"user_id": user_id, "mensagem": msg_user, "historico": historico},
                timeout=30.0,
            )
            latencia = (time.perf_counter() - t0) * 1000
            if resp.status_code == 409:
                logger.info("Onboarding ja concluido — a saltar")
                break
            if resp.status_code != 200:
                logger.warning("HTTP %d: %s", resp.status_code, resp.text[:100])
                break
            data = resp.json()
        except Exception as exc:
            logger.error("T%02d erro: %s", turno, exc)
            break

        msg_assistente = data.get("pergunta", "")
        historico      = data.get("historico_atualizado", historico)
        completo       = data.get("onboarding_completo", False)

        logger.info("T%02d Raquel:  %s", turno, msg_assistente[:70])
        trocas.append(Troca(turno=turno, assistente=msg_assistente,
                            utilizador=msg_user, latencia_ms=round(latencia)))

        if msg_assistente:
            hist_sim.append({"role": "assistant", "content": msg_assistente})
        if msg_user:
            hist_sim.append({"role": "user", "content": msg_user})

        if completo:
            logger.info("Onboarding concluido ao turno %d", turno)
            break
        await asyncio.sleep(2.0)

    return ResultadoSeccao(nome="Onboarding", trocas=trocas)

async def testar_tema(client, token, user_id, tema_id, tema_label) -> ResultadoSeccao:
    logger.info("\n--- TEMA: %s (%d trocas) ---", tema_label, TROCAS_POR_TEMA)
    headers    = {"Authorization": f"Bearer {token}"}
    hist_sim   = []
    trocas     = []
    session_id = None

    for turno in range(1, TROCAS_POR_TEMA + 1):
        msg_user = "Ola" if turno == 1 else simular_resposta(hist_sim, "dashboard")
        logger.info("T%02d Antonio: %s", turno, msg_user[:70])

        t0 = time.perf_counter()
        try:
            resp = await client.post(
                f"{BASE_URL}/chat/conversa/personalizada",
                headers=headers,
                json={"user_id": user_id, "mensagem": msg_user,
                      "tema": tema_id, "session_id": session_id, "historico": None},
                timeout=30.0,
            )
            latencia = (time.perf_counter() - t0) * 1000
            if resp.status_code != 200:
                logger.warning("HTTP %d: %s", resp.status_code, resp.text[:100])
                break
            data = resp.json()
        except Exception as exc:
            logger.error("T%02d erro: %s", turno, exc)
            break

        session_id     = data.get("session_id", session_id)
        msg_assistente = data.get("resposta", "")
        logger.info("T%02d Raquel:  %s", turno, msg_assistente[:70])

        trocas.append(Troca(turno=turno, assistente=msg_assistente,
                            utilizador=msg_user, latencia_ms=round(latencia)))
        hist_sim.append({"role": "assistant", "content": msg_assistente})
        hist_sim.append({"role": "user",      "content": msg_user})
        await asyncio.sleep(2.0)

    return ResultadoSeccao(nome=f"Tema: {tema_label}", trocas=trocas)

SYSTEM_ANALISTA = """\
Es um avaliador de qualidade de VUI (Voice User Interface) para idosos portugueses.
Analisas conversas entre a Raquel (assistente) e o Antonio (idoso simulado).

Avalia:
1. PT-PT: penaliza brasileirismos: "voce", "ta", "ne", "legal", "bacana"
2. TOM: empatico, caloroso. Penaliza: seco, robotico, longo demais
3. TEMA: segue o tema da seccao? Desvia-se desnecessariamente?
4. UMA PERGUNTA: penaliza multiplas perguntas na mesma mensagem
5. CONTEXTO BIOGRAFICO: usa nome e factos do perfil naturalmente?
6. APRESENTACAO: "Ola, chamo-me Raquel" so deve aparecer uma vez
7. LATENCIA: assinala respostas acima de 5000ms

Para cada problema: turno, tipo, excerto, sugestao.
No final, nota exatamente assim: NOTA: X.X/10
Responde em PT-PT de forma concisa.
"""

def analisar_seccao(seccao: ResultadoSeccao) -> tuple[str, float]:
    if not seccao.trocas:
        return "Sem trocas para analisar.", 0.0

    conversa = "\n\n".join(
        f"[T{t.turno} | {t.latencia_ms:.0f}ms]\nAntonio: {t.utilizador}\nRaquel:  {t.assistente}"
        for t in seccao.trocas
    )

    resp = groq_client.chat.completions.create(
        model=MODEL_ANALISE,
        messages=[
            {"role": "system", "content": SYSTEM_ANALISTA},
            {"role": "user",   "content": f"Seccao: {seccao.nome}\n\n{conversa}"},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    texto = resp.choices[0].message.content.strip()

    nota = 0.0
    for linha in texto.split("\n"):
        if "NOTA:" in linha:
            try:
                nota = float(linha.split("NOTA:")[1].split("/")[0].strip())
            except Exception:
                pass
            break

    return texto, nota

async def main(args):
    seccoes: list[ResultadoSeccao] = []

    async with httpx.AsyncClient() as client:
        try:
            token, user_id = await login(client)
        except Exception as exc:
            logger.error("Login falhou: %s", exc)
            sys.exit(1)

        if args.onboarding or not args.tema:
            seccoes.append(await testar_onboarding(client, token, user_id))

        temas = TEMAS
        if args.tema:
            temas = [(t, l) for t, l in TEMAS if t == args.tema]
            if not temas:
                logger.error("Tema '%s' invalido. Disponiveis: %s", args.tema, [t for t,_ in TEMAS])
                sys.exit(1)

        if not args.onboarding:
            for i, (tema_id, tema_label) in enumerate(temas):
                if i > 0:
                    logger.info("Pausa entre temas (5s)...")
                    await asyncio.sleep(5.0)
                seccoes.append(await testar_tema(client, token, user_id, tema_id, tema_label))

    sep = "=" * 60
    print(f"\n{sep}\n  RELATORIO COMPLETO — MEMORIAS VIVAS")
    print(f"  {sum(len(s.trocas) for s in seccoes)} trocas | {len(seccoes)} seccoes\n{sep}")

    notas = []
    relatorio_json = {}

    for sec in seccoes:
        logger.info("A analisar: %s...", sec.nome)
        sec.relatorio, sec.nota = analisar_seccao(sec)
        notas.append(sec.nota)
        relatorio_json[sec.nome] = {
            "nota": sec.nota,
            "relatorio": sec.relatorio,
            "trocas": [{"turno": t.turno, "assistente": t.assistente,
                        "utilizador": t.utilizador, "latencia_ms": t.latencia_ms}
                       for t in sec.trocas],
        }
        print(f"\n{'-'*60}\n  {sec.nome.upper()} — NOTA: {sec.nota:.1f}/10\n{'-'*60}")
        print(sec.relatorio)

    if notas:
        media = sum(notas) / len(notas)
        print(f"\n{sep}\n  NOTA GLOBAL: {media:.1f}/10")
        print("  " + " | ".join(f"{s.nome}: {s.nota:.1f}" for s in seccoes))
        print(sep)

    with open("/tmp/relatorio_teste.json", "w", encoding="utf-8") as f:
        json.dump(relatorio_json, f, ensure_ascii=False, indent=2)
    logger.info("Guardado em /tmp/relatorio_teste.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--onboarding", action="store_true", help="Apenas onboarding")
    parser.add_argument("--tema", type=str, default=None, help="Apenas um tema")
    asyncio.run(main(parser.parse_args()))