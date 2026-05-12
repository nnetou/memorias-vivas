"""
app/api/artefactos.py — Router FastAPI para geração e download de artefactos (Epic 6).

Endpoints:
    POST /api/v1/artefactos/livro-memorias    → gera PDF livro de memórias
    POST /api/v1/artefactos/timeline          → gera HTML timeline
    POST /api/v1/artefactos/cartoes           → gera PDF story cards
    POST /api/v1/artefactos/video             → gera MP4 (background task)
    GET  /api/v1/artefactos/                  → lista artefactos do utilizador
    GET  /api/v1/artefactos/{id}/download     → download do ficheiro
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.utilizador import Artefacto, PerfilBiografico, Sessao, Utilizador
from app.services import artefactos_service
from app.services.profile_service import get_profile

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ArtefactoInput(BaseModel):
    user_id: str = Field(..., description="UUID do utilizador")


class ArtefactoOut(BaseModel):
    id: str
    tipo: str
    url_download: str
    gerado_em: str
    meta_dados: dict | None = None


class ListaArtefactosOut(BaseModel):
    artefactos: list[ArtefactoOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_sessoes(user_id: str, db: AsyncSession) -> list[dict]:
    """Carrega sessões com resumo do PostgreSQL."""
    result = await db.execute(
        select(Sessao)
        .where(Sessao.utilizador_id == uuid.UUID(user_id))
        .order_by(Sessao.criada_em)
    )
    sessoes = result.scalars().all()
    return [
        {
            "tema": s.tema or "geral",
            "resumo_sessao": s.resumo_sessao,
            "criada_em": s.criada_em.strftime("%d/%m/%Y") if s.criada_em else "",
        }
        for s in sessoes
    ]


async def _get_temas(user_id: str, db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(PerfilBiografico.temas_explorados)
        .where(PerfilBiografico.utilizador_id == uuid.UUID(user_id))
    )
    row = result.scalar_one_or_none()
    return row or []


async def _get_nome(user_id: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(Utilizador.nome).where(Utilizador.id == uuid.UUID(user_id))
    )
    return result.scalar_one_or_none() or "Memórias"


async def _persistir_artefacto(
    user_id: str,
    tipo: str,
    caminho: Path,
    meta: dict,
    db: AsyncSession,
) -> Artefacto:
    arte = Artefacto(
        utilizador_id=uuid.UUID(user_id),
        tipo=tipo,
        url_ficheiro=str(caminho),
        meta_dados=meta,
    )
    db.add(arte)
    await db.commit()
    await db.refresh(arte)
    return arte


def _arte_out(arte: Artefacto) -> ArtefactoOut:
    return ArtefactoOut(
        id=str(arte.id),
        tipo=arte.tipo,
        url_download=f"/api/v1/artefactos/{arte.id}/download",
        gerado_em=arte.gerado_em.strftime("%d/%m/%Y %H:%M") if arte.gerado_em else "",
        meta_dados=arte.meta_dados,
    )


# ---------------------------------------------------------------------------
# POST /livro-memorias
# ---------------------------------------------------------------------------

@router.post("/livro-memorias", response_model=ArtefactoOut)
async def gerar_livro_memorias(
    payload: ArtefactoInput,
    db: AsyncSession = Depends(get_db),
):
    """Gera o livro de memórias em PDF com capítulos por tema."""
    perfil_db = await get_profile(payload.user_id, db)
    nome      = await _get_nome(payload.user_id, db)
    sessoes   = await _get_sessoes(payload.user_id, db)

    try:
        caminho = await artefactos_service.gerar_livro_pdf(
            user_id=payload.user_id,
            perfil_json=perfil_db.perfil_json if perfil_db else None,
            sessoes=sessoes,
            nome=nome,
        )
    except Exception as exc:
        logger.exception("Erro ao gerar livro PDF: %s", exc)
        raise HTTPException(status_code=500, detail=f"Erro na geração do PDF: {exc}")

    arte = await _persistir_artefacto(
        payload.user_id, "livro_pdf", caminho,
        {"nome": nome, "n_sessoes": len(sessoes)}, db,
    )
    return _arte_out(arte)


# ---------------------------------------------------------------------------
# POST /timeline
# ---------------------------------------------------------------------------

@router.post("/timeline", response_model=ArtefactoOut)
async def gerar_timeline(
    payload: ArtefactoInput,
    db: AsyncSession = Depends(get_db),
):
    """Gera a linha temporal interativa em HTML standalone."""
    perfil_db = await get_profile(payload.user_id, db)
    nome      = await _get_nome(payload.user_id, db)

    try:
        caminho = await artefactos_service.gerar_timeline(
            user_id=payload.user_id,
            perfil_json=perfil_db.perfil_json if perfil_db else None,
            nome=nome,
        )
    except Exception as exc:
        logger.exception("Erro ao gerar timeline: %s", exc)
        raise HTTPException(status_code=500, detail=f"Erro na geração da timeline: {exc}")

    arte = await _persistir_artefacto(
        payload.user_id, "timeline_html", caminho, {"nome": nome}, db,
    )
    return _arte_out(arte)


# ---------------------------------------------------------------------------
# POST /cartoes
# ---------------------------------------------------------------------------

@router.post("/cartoes", response_model=ArtefactoOut)
async def gerar_cartoes(
    payload: ArtefactoInput,
    db: AsyncSession = Depends(get_db),
):
    """Gera cartões de histórias PDF (um por tema explorado)."""
    perfil_db = await get_profile(payload.user_id, db)
    nome      = await _get_nome(payload.user_id, db)
    sessoes   = await _get_sessoes(payload.user_id, db)

    try:
        caminho = await artefactos_service.gerar_cartoes_pdf(
            user_id=payload.user_id,
            perfil_json=perfil_db.perfil_json if perfil_db else None,
            sessoes=sessoes,
            nome=nome,
        )
    except Exception as exc:
        logger.exception("Erro ao gerar cartões: %s", exc)
        raise HTTPException(status_code=500, detail=f"Erro na geração dos cartões: {exc}")

    arte = await _persistir_artefacto(
        payload.user_id, "cartoes_pdf", caminho,
        {"nome": nome, "n_sessoes": len(sessoes)}, db,
    )
    return _arte_out(arte)


# ---------------------------------------------------------------------------
# POST /video  (pode demorar 30–90s — usa BackgroundTasks)
# ---------------------------------------------------------------------------

class VideoStatusOut(BaseModel):
    mensagem: str
    artefacto_id: str | None = None


@router.post("/video", response_model=ArtefactoOut)
async def gerar_video(
    payload: ArtefactoInput,
    db: AsyncSession = Depends(get_db),
):
    """Gera vídeo curto ilustrativo (30-90s) com narração TTS e slideshow."""
    perfil_db = await get_profile(payload.user_id, db)
    nome      = await _get_nome(payload.user_id, db)
    temas     = await _get_temas(payload.user_id, db)

    try:
        caminho = await artefactos_service.gerar_video(
            user_id=payload.user_id,
            perfil_json=perfil_db.perfil_json if perfil_db else None,
            nome=nome,
            temas=temas or ["memorias"],
        )
    except Exception as exc:
        logger.exception("Erro ao gerar vídeo: %s", exc)
        raise HTTPException(status_code=500, detail=f"Erro na geração do vídeo: {exc}")

    arte = await _persistir_artefacto(
        payload.user_id, "video_mp4", caminho,
        {"nome": nome, "temas": temas}, db,
    )
    return _arte_out(arte)


# ---------------------------------------------------------------------------
# GET /  — lista artefactos do utilizador
# ---------------------------------------------------------------------------

@router.get("/", response_model=ListaArtefactosOut)
async def listar_artefactos(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Lista todos os artefactos gerados pelo utilizador."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="user_id inválido")

    result = await db.execute(
        select(Artefacto)
        .where(Artefacto.utilizador_id == uid)
        .order_by(Artefacto.gerado_em.desc())
    )
    artefactos = result.scalars().all()
    return ListaArtefactosOut(artefactos=[_arte_out(a) for a in artefactos])


# ---------------------------------------------------------------------------
# GET /{artefacto_id}/download
# ---------------------------------------------------------------------------

@router.get("/{artefacto_id}/download")
async def download_artefacto(
    artefacto_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve o ficheiro gerado para download."""
    try:
        aid = uuid.UUID(artefacto_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="artefacto_id inválido")

    result = await db.execute(select(Artefacto).where(Artefacto.id == aid))
    arte = result.scalar_one_or_none()
    if not arte:
        raise HTTPException(status_code=404, detail="Artefacto não encontrado")

    caminho = Path(arte.url_ficheiro)
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Ficheiro não encontrado no servidor")

    media_type_map = {
        "livro_pdf":   "application/pdf",
        "cartoes_pdf": "application/pdf",
        "timeline_html": "text/html",
        "video_mp4":   "video/mp4",
    }
    media_type = media_type_map.get(arte.tipo, "application/octet-stream")

    return FileResponse(
        path=str(caminho),
        media_type=media_type,
        filename=caminho.name,
    )
