"""
app/services/auth_service.py — Autenticação JWT + bcrypt para o projeto Memórias Vivas.

Responsabilidades:
    - Hash e verificação de passwords (bcrypt via passlib)
    - Criação e validação de JWT de acesso e refresh
    - Geração e verificação de tokens de reset de password
    - Dependency FastAPI: get_current_user / get_current_active_user

Tokens:
    access_token   — TTL configurável (default 30 min), enviado no header Authorization
    refresh_token  — TTL 7 dias, permite renovar o access_token sem novo login
    reset_token    — TTL 1 hora, enviado por email, hash SHA-256 guardado na DB
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models.utilizador import TokenResetPassword, Utilizador

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ALGORITHM      = "HS256"
TOKEN_TYPE     = "Bearer"
RESET_TTL_H    = 1    # horas — token de reset de password
REFRESH_TTL_D  = 7    # dias  — refresh token


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Gera hash bcrypt da password."""
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verifica password em texto simples contra hash bcrypt."""
    return _pwd_context.verify(password, hashed)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def _criar_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def criar_access_token(user_id: str, role: str) -> str:
    return _criar_token(
        {"sub": user_id, "role": role, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def criar_refresh_token(user_id: str) -> str:
    return _criar_token(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=REFRESH_TTL_D),
    )


def decode_token(token: str) -> dict:
    """
    Valida e descodifica um JWT.

    Raises:
        HTTPException 401 se o token for inválido ou expirado.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Reset de password
# ---------------------------------------------------------------------------

def gerar_reset_token() -> tuple[str, str]:
    """
    Gera um par (token_plaintext, token_hash).

    O token_plaintext é enviado por email ao utilizador.
    O token_hash (SHA-256) é guardado na base de dados.

    Returns:
        (token_plaintext, token_hash)
    """
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def hash_reset_token(token: str) -> str:
    """Converte token plaintext em hash para comparação com a DB."""
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# DB helpers de autenticação
# ---------------------------------------------------------------------------

async def get_user_by_email(
    email: str,
    db: AsyncSession,
) -> Optional[Utilizador]:
    result = await db.execute(
        select(Utilizador).where(Utilizador.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(
    user_id: str,
    db: AsyncSession,
) -> Optional[Utilizador]:
    uid = uuid.UUID(user_id)
    result = await db.execute(select(Utilizador).where(Utilizador.id == uid))
    return result.scalar_one_or_none()


async def criar_token_reset_db(
    utilizador_id: uuid.UUID,
    token_hash: str,
    db: AsyncSession,
) -> TokenResetPassword:
    """Persiste o token de reset na DB com TTL de 1 hora."""
    token_db = TokenResetPassword(
        utilizador_id=utilizador_id,
        token_hash=token_hash,
        expira_em=datetime.now(timezone.utc) + timedelta(hours=RESET_TTL_H),
    )
    db.add(token_db)
    await db.flush()
    return token_db


async def validar_token_reset_db(
    token_plaintext: str,
    db: AsyncSession,
) -> TokenResetPassword:
    """
    Valida um token de reset de password.

    Raises:
        HTTPException 400 se o token não existir, já foi usado, ou expirou.
    """
    token_hash = hash_reset_token(token_plaintext)
    result = await db.execute(
        select(TokenResetPassword).where(
            TokenResetPassword.token_hash == token_hash
        )
    )
    token_db = result.scalar_one_or_none()

    if token_db is None:
        raise HTTPException(status_code=400, detail="Token inválido.")
    if token_db.usado:
        raise HTTPException(status_code=400, detail="Token já utilizado.")
    if token_db.expira_em.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expirado. Solicite um novo.")

    return token_db


# ---------------------------------------------------------------------------
# Dependencies FastAPI
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Utilizador:
    """
    Dependency — extrai e valida o JWT do header Authorization.
    Injeta o Utilizador autenticado nos endpoints protegidos.
    """
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tipo de token inválido.",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem identificador de utilizador.",
        )

    user = await get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador não encontrado.",
        )
    return user


async def get_current_active_user(
    current_user: Utilizador = Depends(get_current_user),
) -> Utilizador:
    """
    Dependency — garante que o utilizador está ativo.
    Usar em todos os endpoints que requerem autenticação.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Contacte o administrador.",
        )
    return current_user