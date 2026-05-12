"""
app/services/artefactos_service.py — Geração de artefactos de portfólio (Epic 6).

6.1  gerar_livro_pdf()   → WeasyPrint PDF  (livro de memórias por capítulos)
6.2  gerar_timeline()    → HTML standalone (linha temporal interativa)
6.3  gerar_cartoes_pdf() → WeasyPrint PDF  (story cards A5 landscape)
6.4  gerar_video()       → MoviePy MP4     (slideshow narrado 30-90s)
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Diretório de saída — mapeado como volume Docker
# ---------------------------------------------------------------------------
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/media/artefactos"))

TEMAS_LABELS: dict[str, str] = {
    "memorias":       "Memórias",
    "familia":        "Família",
    "saude":          "Bem-estar",
    "entretenimento": "Entretenimento",
    "exercicio":      "Exercício",
    "geral":          "Conversa livre",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_dir(user_id: str) -> Path:
    d = MEDIA_ROOT / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _data_pt() -> str:
    now = datetime.now(timezone.utc)
    meses = ["janeiro","fevereiro","março","abril","maio","junho",
              "julho","agosto","setembro","outubro","novembro","dezembro"]
    return f"{now.day} de {meses[now.month-1]} de {now.year}"


def _jinja_env() -> Environment:
    tpl_dir = Path(__file__).parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(tpl_dir)), autoescape=True)


def _perfil_safe(perfil_json: dict | None) -> dict:
    """Garante valores padrão para todos os campos do perfil."""
    p = perfil_json or {}
    defaults: dict[str, Any] = {
        "nome": None, "terra_natal": None, "familia": None,
        "profissao": None, "memoria_marcante": None,
        "pessoas": [], "locais": [], "datas_aproximadas": [],
        "eventos_marcantes": [], "tradicoes": [], "expressoes_regionais": [],
        "momentos_chave": [], "resumo_narrativo": None, "outros": {},
    }
    return {**defaults, **p}


# ---------------------------------------------------------------------------
# 6.1 — Livro de Memórias PDF
# ---------------------------------------------------------------------------

def _gerar_livro_pdf_sync(
    user_id: str,
    perfil_json: dict | None,
    sessoes: list[dict],
    nome: str,
) -> Path:
    from weasyprint import HTML as WPhtml

    p = _perfil_safe(perfil_json)
    env = _jinja_env()
    tmpl = env.get_template("livro_memorias.html")

    sessoes_ctx = [
        {
            "tema_label": TEMAS_LABELS.get(s.get("tema", "geral"), s.get("tema", "")),
            "titulo": f"{TEMAS_LABELS.get(s.get('tema','geral'), '')} — recordações",
            "resumo": s.get("resumo_sessao") or "",
            "data": s.get("criada_em", ""),
        }
        for s in sessoes
        if s.get("resumo_sessao")
    ]

    html_str = tmpl.render(
        nome=nome or "Memórias",
        data_geracao=_data_pt(),
        resumo_narrativo=p["resumo_narrativo"],
        terra_natal=p["terra_natal"],
        profissao=p["profissao"],
        familia=p["familia"],
        memoria_marcante=p["memoria_marcante"],
        pessoas=p["pessoas"],
        locais=p["locais"],
        eventos_marcantes=p["eventos_marcantes"],
        momentos_chave=p["momentos_chave"],
        tradicoes=p["tradicoes"],
        sessoes=sessoes_ctx,
    )

    out = _user_dir(user_id) / f"livro_memorias_{_ts()}.pdf"
    WPhtml(string=html_str).write_pdf(str(out))
    logger.info("Livro PDF gerado: %s", out)
    return out


async def gerar_livro_pdf(
    user_id: str,
    perfil_json: dict | None,
    sessoes: list[dict],
    nome: str,
) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _gerar_livro_pdf_sync, user_id, perfil_json, sessoes, nome
    )


# ---------------------------------------------------------------------------
# 6.2 — Timeline HTML standalone
# ---------------------------------------------------------------------------

def _gerar_timeline_html_sync(
    user_id: str,
    perfil_json: dict | None,
    nome: str,
) -> Path:
    p = _perfil_safe(perfil_json)

    eventos: list[dict] = []
    for ev in p["eventos_marcantes"]:
        eventos.append({"tipo": "evento", "descricao": ev, "periodo": ""})
    for mc in p["momentos_chave"]:
        eventos.append({"tipo": "momento", "descricao": mc, "periodo": ""})
    for i, da in enumerate(p["datas_aproximadas"]):
        if i < len(eventos):
            eventos[i]["periodo"] = da
        else:
            eventos.append({"tipo": "data", "descricao": da, "periodo": da})

    items_html = ""
    for i, ev in enumerate(eventos):
        side = "left" if i % 2 == 0 else "right"
        icon_color = "#1e3a5f" if ev["tipo"] == "evento" else "#c9a84c"
        items_html += f"""
        <div class="timeline-item {side}">
          <div class="timeline-dot" style="background:{icon_color}"></div>
          <div class="timeline-content">
            {"<span class='timeline-periodo'>" + ev['periodo'] + "</span>" if ev['periodo'] else ""}
            <p class="timeline-desc">{ev['descricao']}</p>
          </div>
        </div>"""

    if not items_html:
        items_html = "<p class='empty'>Ainda não há eventos registados para a linha temporal.</p>"

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linha Temporal — {nome}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=Lora:wght@400;500&display=swap');
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Lora',serif;background:#FAF7F2;color:#1a1a2e;min-height:100vh}}
  header{{background:#1e3a5f;padding:32px 40px;text-align:center}}
  header h1{{font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:300;color:#FAF7F2;letter-spacing:2px}}
  header p{{color:#7a9cbf;margin-top:8px;font-size:1.1rem}}
  .ornamento{{width:40px;height:2px;background:#c9a84c;margin:12px auto 0}}
  .container{{max-width:900px;margin:0 auto;padding:60px 20px}}
  .timeline{{position:relative;padding:20px 0}}
  .timeline::before{{content:'';position:absolute;left:50%;top:0;bottom:0;width:2px;background:#e8e0d5;transform:translateX(-50%)}}
  .timeline-item{{display:flex;width:100%;margin-bottom:40px;position:relative}}
  .timeline-item.left{{justify-content:flex-end;padding-right:calc(50% + 30px)}}
  .timeline-item.right{{justify-content:flex-start;padding-left:calc(50% + 30px)}}
  .timeline-dot{{position:absolute;left:50%;top:12px;width:14px;height:14px;border-radius:50%;transform:translateX(-50%);border:2px solid #FAF7F2;box-shadow:0 0 0 2px #c9a84c}}
  .timeline-content{{background:#fff;border:1px solid #e8e0d5;padding:20px 24px;max-width:360px;box-shadow:0 2px 8px rgba(0,0,0,.05)}}
  .timeline-content:hover{{border-color:#1e3a5f;transform:translateY(-2px);transition:all .2s}}
  .timeline-periodo{{display:block;font-size:.75rem;letter-spacing:2px;text-transform:uppercase;color:#c9a84c;margin-bottom:8px}}
  .timeline-desc{{font-size:1rem;line-height:1.7;color:#2a2a4e}}
  .empty{{text-align:center;color:#aaa;font-size:1.1rem;padding:60px 20px}}
  footer{{text-align:center;padding:40px;color:#bbb;font-size:.85rem;letter-spacing:1px;border-top:1px solid #e8e0d5;margin-top:40px}}
  @media(max-width:600px){{
    .timeline::before{{left:20px}}
    .timeline-item.left,.timeline-item.right{{justify-content:flex-start;padding-left:50px;padding-right:0}}
    .timeline-dot{{left:20px}}
    .timeline-content{{max-width:100%}}
  }}
</style>
</head>
<body>
<header>
  <h1>Linha Temporal</h1>
  <p>{nome}</p>
  <div class="ornamento"></div>
</header>
<div class="container">
  <div class="timeline">{items_html}</div>
</div>
<footer>Memórias Vivas · Gerado por IA · {_data_pt()}</footer>
</body>
</html>"""

    out = _user_dir(user_id) / f"timeline_{_ts()}.html"
    out.write_text(html, encoding="utf-8")
    logger.info("Timeline HTML gerada: %s", out)
    return out


async def gerar_timeline(
    user_id: str,
    perfil_json: dict | None,
    nome: str,
) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _gerar_timeline_html_sync, user_id, perfil_json, nome
    )


# ---------------------------------------------------------------------------
# 6.3 — Cartões de Histórias PDF
# ---------------------------------------------------------------------------

def _gerar_cartoes_pdf_sync(
    user_id: str,
    perfil_json: dict | None,
    sessoes: list[dict],
    nome: str,
) -> Path:
    from weasyprint import HTML as WPhtml

    p = _perfil_safe(perfil_json)
    env = _jinja_env()
    tmpl = env.get_template("story_card.html")

    temas_vistos: set[str] = set()
    cartoes = []
    for s in sessoes:
        tema = s.get("tema", "geral")
        if tema in temas_vistos:
            continue
        temas_vistos.add(tema)
        cartoes.append({
            "tema_label": TEMAS_LABELS.get(tema, tema),
            "resumo": s.get("resumo_sessao") or p.get("resumo_narrativo") or "",
            "facto_destaque": {
                "terra_natal": p["terra_natal"],
                "profissao": p["profissao"],
                "data": p["datas_aproximadas"][0] if p["datas_aproximadas"] else None,
            },
        })

    # Garante pelo menos um cartão mesmo sem sessões
    if not cartoes:
        cartoes.append({
            "tema_label": "Memórias",
            "resumo": p["resumo_narrativo"] or "Uma vida rica em histórias.",
            "facto_destaque": {
                "terra_natal": p["terra_natal"],
                "profissao": p["profissao"],
                "data": None,
            },
        })

    html_str = tmpl.render(
        nome=nome or "Memórias",
        data_geracao=_data_pt(),
        cartoes=cartoes,
    )

    out = _user_dir(user_id) / f"cartoes_{_ts()}.pdf"
    WPhtml(string=html_str).write_pdf(str(out))
    logger.info("Cartões PDF gerados: %s", out)
    return out


async def gerar_cartoes_pdf(
    user_id: str,
    perfil_json: dict | None,
    sessoes: list[dict],
    nome: str,
) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _gerar_cartoes_pdf_sync, user_id, perfil_json, sessoes, nome
    )


# ---------------------------------------------------------------------------
# 6.4 — Vídeo curto (MoviePy + Pillow + edge-tts)
# ---------------------------------------------------------------------------

_TEMA_GRADIENTES: dict[str, tuple[str, str]] = {
    "memorias":       ("#1e3a5f", "#4a7ab5"),
    "familia":        ("#3d2b1f", "#c9a84c"),
    "saude":          ("#1a4a2e", "#5aab6e"),
    "entretenimento": ("#2b1a4a", "#8b6fd8"),
    "exercicio":      ("#4a1e1e", "#c95a5a"),
    "geral":          ("#2a2a3e", "#7a9cbf"),
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore


def _criar_frame_pillow(
    texto: str,
    subtitulo: str,
    cor1: str,
    cor2: str,
    width: int = 1280,
    height: int = 720,
) -> "Image":
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    r1, g1, b1 = _hex_to_rgb(cor1)
    r2, g2, b2 = _hex_to_rgb(cor2)
    for y in range(height):
        t = y / height
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Gold accent bar
    draw.rectangle([(60, height // 2 - 2), (160, height // 2 + 2)], fill=(201, 168, 76))

    # Title text
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 64)
        font_sub   = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        font_label = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except Exception:
        font_title = font_sub = font_label = ImageFont.load_default()

    # Shadow + title
    draw.text((62, height // 2 - 80), texto, font=font_title, fill=(0, 0, 0, 80))
    draw.text((60, height // 2 - 82), texto, font=font_title, fill=(250, 247, 242))

    if subtitulo:
        draw.text((62, height // 2 + 20), subtitulo, font=font_sub, fill=(160, 190, 220))

    # AI label bottom-right
    draw.text((width - 320, height - 44), "Gerado por IA · Memórias Vivas",
              font=font_label, fill=(100, 130, 160))

    return img


def _gerar_video_sync(
    user_id: str,
    perfil_json: dict | None,
    nome: str,
    temas: list[str],
) -> Path:
    import numpy as np
    from moviepy.editor import (
        AudioFileClip, CompositeVideoClip, ImageClip,
        TextClip, concatenate_videoclips,
    )

    p = _perfil_safe(perfil_json)
    frames_info: list[tuple[str, str, str, str]] = []

    # Slide de abertura
    frames_info.append(("Memórias Vivas", nome or "As minhas memórias", "#1e3a5f", "#4a7ab5"))

    # Um slide por tema explorado
    for tema in (temas or ["memorias"]):
        cor1, cor2 = _TEMA_GRADIENTES.get(tema, ("#1e3a5f", "#4a7ab5"))
        label = TEMAS_LABELS.get(tema, tema)
        frames_info.append((label, f"{nome} conta as suas histórias", cor1, cor2))

    # Slide de encerramento
    if p["resumo_narrativo"]:
        words = p["resumo_narrativo"].split()
        resumo_curto = " ".join(words[:12]) + ("…" if len(words) > 12 else "")
        frames_info.append((resumo_curto, "", "#1e3a5f", "#163050"))
    else:
        frames_info.append(("Obrigado por partilhar", "As suas memórias ficam para sempre", "#1e3a5f", "#163050"))

    clips = []
    duration_per_slide = max(4, min(8, 60 // len(frames_info)))

    for titulo, subtitulo, c1, c2 in frames_info:
        img = _criar_frame_pillow(titulo, subtitulo, c1, c2)
        arr = np.array(img)
        clip = ImageClip(arr, duration=duration_per_slide)
        clip = clip.fadein(0.5).fadeout(0.5)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    # Narração TTS (edge-tts, síncrono via asyncio.run em executor)
    narration_text = (
        f"Memórias Vivas. As memórias de {nome}. "
        + (p["resumo_narrativo"] or "Uma vida rica em histórias e momentos únicos.")
    )
    narration_text = narration_text[:500]  # limitar para TTS rápido

    tmp_audio = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        asyncio.run(_tts_para_ficheiro(narration_text, str(tmp_audio)))
        audio = AudioFileClip(str(tmp_audio))
        # Ajustar duração do vídeo ao áudio ou ao contrário
        if audio.duration < video.duration:
            audio = audio.audio_loop(duration=video.duration)
        else:
            video = video.set_duration(audio.duration)
        video = video.set_audio(audio)
    except Exception as exc:
        logger.warning("TTS falhou, vídeo sem áudio: %s", exc)

    out = _user_dir(user_id) / f"video_{_ts()}.mp4"
    video.write_videofile(
        str(out),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    video.close()
    if tmp_audio.exists():
        tmp_audio.unlink(missing_ok=True)

    logger.info("Vídeo gerado: %s", out)
    return out


async def _tts_para_ficheiro(texto: str, caminho: str) -> None:
    """Gera narração TTS em PT-PT via edge-tts e guarda em ficheiro."""
    import edge_tts
    communicate = edge_tts.Communicate(texto, voice="pt-PT-RaquelNeural")
    await communicate.save(caminho)


async def gerar_video(
    user_id: str,
    perfil_json: dict | None,
    nome: str,
    temas: list[str],
) -> Path:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _gerar_video_sync, user_id, perfil_json, nome, temas
    )
