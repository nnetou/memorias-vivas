"""
utilizador.py — Modelos ORM SQLAlchemy para as tabelas de utilizadores e perfis.

Tabelas:
    utilizadores          : registo base do idoso (UUID, nome, onboarding_completo)
    perfis_biograficos    : perfil JSON acumulado + temas explorados (JSONB)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Tabela: utilizadores
# ---------------------------------------------------------------------------
class Utilizador(Base):
    __tablename__ = "utilizadores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    onboarding_completo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Relação 1-1 para o perfil biográfico
    perfil: Mapped["PerfilBiografico | None"] = relationship(
        "PerfilBiografico",
        back_populates="utilizador",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Utilizador id={self.id} onboarding={self.onboarding_completo}>"


# ---------------------------------------------------------------------------
# Tabela: perfis_biograficos
# ---------------------------------------------------------------------------
class PerfilBiografico(Base):
    """
    Perfil biográfico persistente do idoso (memória longa).

    perfil_json exemplo:
    {
        "nome": "Maria",
        "terra_natal": "Évora",
        "familia": "Tem 3 filhos e 5 netos",
        "profissao": "Professora primária",
        "memoria_marcante": "O dia do casamento na aldeia"
    }

    temas_explorados: lista de chaves de tema já abordados (ex: ["infancia", "trabalho"])
    """

    __tablename__ = "perfis_biograficos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    utilizador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilizadores.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Perfil extraído pelo Gemini após onboarding
    perfil_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Temas já explorados em sessões anteriores
    temas_explorados: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    # Historial de onboarding (mensagens brutas para referência)
    historico_onboarding: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Relação inversa
    utilizador: Mapped["Utilizador"] = relationship(
        "Utilizador", back_populates="perfil"
    )

    def __repr__(self) -> str:
        nome = (self.perfil_json or {}).get("nome", "?")
        return f"<PerfilBiografico utilizador={self.utilizador_id} nome={nome}>"
