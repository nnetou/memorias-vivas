"""
app/models/utilizador.py — Modelos SQLAlchemy para o projeto Memórias Vivas.

Tabelas:
    utilizadores            — identidade, autenticação e estado do idoso
    tokens_reset_password   — tokens de recuperação de password (TTL 1h)
    perfis_biograficos      — memória longa (JSONB, LangGraph merge)
    sessoes                 — registo de cada conversa individual
    consentimentos          — conformidade RGPD (Epic 7.2)
    artefactos              — ficheiros gerados (Epic 6): PDF, MP4, HTML
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Enum de papéis
# ---------------------------------------------------------------------------

class RoleEnum(str, enum.Enum):
    administrador = "administrador"
    cuidador      = "cuidador"
    idoso         = "idoso"


# ---------------------------------------------------------------------------
# Tabela: utilizadores
# ---------------------------------------------------------------------------

class Utilizador(Base):
    __tablename__ = "utilizadores"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_uuid,
        comment="UUID do utilizador.",
    )

    # ── Autenticação ─────────────────────────────────────────────────────────
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="Email único — usado para login e recuperação de password.",
    )
    password_hash = Column(
        Text,
        nullable=False,
        comment="Hash bcrypt da password. Nunca armazenar plaintext.",
    )
    role = Column(
        Enum(RoleEnum, name="role_enum"),
        nullable=False,
        default=RoleEnum.idoso,
        comment="Papel do utilizador: administrador, cuidador ou idoso.",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="False para contas desativadas (RGPD: direito ao esquecimento).",
    )
    ultimo_login = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp do último login com sucesso.",
    )

    # ── Perfil biográfico ────────────────────────────────────────────────────
    nome = Column(String(255), nullable=True)
    onboarding_completo = Column(Boolean, nullable=False, default=False)

    # ── Timestamps ───────────────────────────────────────────────────────────
    criado_em    = Column(DateTime(timezone=True), nullable=False, default=_now)
    atualizado_em = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    # ── Relações ─────────────────────────────────────────────────────────────
    perfil         = relationship("PerfilBiografico",     back_populates="utilizador",
                                  uselist=False, cascade="all, delete-orphan")
    sessoes        = relationship("Sessao",                back_populates="utilizador",
                                  cascade="all, delete-orphan")
    consentimentos = relationship("Consentimento",         back_populates="utilizador",
                                  cascade="all, delete-orphan")
    artefactos     = relationship("Artefacto",             back_populates="utilizador",
                                  cascade="all, delete-orphan")
    tokens_reset   = relationship("TokenResetPassword",    back_populates="utilizador",
                                  cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Utilizador email={self.email!r} role={self.role}>"


# ---------------------------------------------------------------------------
# Tabela: tokens_reset_password
# ---------------------------------------------------------------------------

class TokenResetPassword(Base):
    __tablename__ = "tokens_reset_password"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    utilizador_id = Column(
        UUID(as_uuid=True),
        ForeignKey("utilizadores.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="Hash SHA-256 do token enviado por email. Nunca guardar o token em plaintext.",
    )
    expira_em = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="TTL de 1 hora após criação.",
    )
    usado = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="True após o token ser consumido — não pode ser reutilizado.",
    )
    criado_em = Column(DateTime(timezone=True), nullable=False, default=_now)

    utilizador = relationship("Utilizador", back_populates="tokens_reset")

    def __repr__(self) -> str:
        return f"<TokenResetPassword utilizador_id={self.utilizador_id} usado={self.usado}>"


# ---------------------------------------------------------------------------
# Tabela: perfis_biograficos
# ---------------------------------------------------------------------------

class PerfilBiografico(Base):
    __tablename__ = "perfis_biograficos"
    __table_args__ = (
        UniqueConstraint("utilizador_id", name="uq_perfil_utilizador"),
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    utilizador_id = Column(UUID(as_uuid=True),
                           ForeignKey("utilizadores.id", ondelete="CASCADE"),
                           nullable=False)
    perfil_json           = Column(JSONB,          nullable=True)
    temas_explorados      = Column(ARRAY(String()), nullable=False, default=list)
    historico_onboarding  = Column(JSONB,          nullable=True)
    atualizado_em         = Column(DateTime(timezone=True), nullable=False,
                                   default=_now, onupdate=_now)

    utilizador = relationship("Utilizador", back_populates="perfil")


# ---------------------------------------------------------------------------
# Tabela: sessoes
# ---------------------------------------------------------------------------

class Sessao(Base):
    __tablename__ = "sessoes"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    utilizador_id    = Column(UUID(as_uuid=True),
                              ForeignKey("utilizadores.id", ondelete="CASCADE"),
                              nullable=False)
    session_id_redis = Column(String(100), nullable=True)
    tema             = Column(String(50),  nullable=True)
    resumo_sessao    = Column(Text,        nullable=True)
    criada_em        = Column(DateTime(timezone=True), nullable=False, default=_now)

    utilizador = relationship("Utilizador", back_populates="sessoes")


# ---------------------------------------------------------------------------
# Tabela: consentimentos
# ---------------------------------------------------------------------------

class Consentimento(Base):
    __tablename__ = "consentimentos"

    id                        = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    utilizador_id             = Column(UUID(as_uuid=True),
                                       ForeignKey("utilizadores.id", ondelete="CASCADE"),
                                       nullable=False)
    autoriza_gravacao_voz     = Column(Boolean, nullable=False, default=False)
    autoriza_processamento_ia = Column(Boolean, nullable=False, default=False)
    autoriza_geracao_video    = Column(Boolean, nullable=False, default=False)
    data_assinatura           = Column(DateTime(timezone=True), nullable=False, default=_now)

    utilizador = relationship("Utilizador", back_populates="consentimentos")


# ---------------------------------------------------------------------------
# Tabela: artefactos
# ---------------------------------------------------------------------------

class Artefacto(Base):
    __tablename__ = "artefactos"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    utilizador_id = Column(UUID(as_uuid=True),
                           ForeignKey("utilizadores.id", ondelete="CASCADE"),
                           nullable=False)
    tipo          = Column(String(20), nullable=False)
    url_ficheiro  = Column(Text,       nullable=True)
    meta_dados    = Column(JSONB,      nullable=True)
    gerado_em     = Column(DateTime(timezone=True), nullable=False, default=_now)

    utilizador = relationship("Utilizador", back_populates="artefactos")