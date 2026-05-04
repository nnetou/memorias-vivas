"""
app/api/auth.py — Endpoints de autenticação do projeto Memórias Vivas.

Endpoints:
    POST /api/v1/auth/registar           → criar conta
    POST /api/v1/auth/login              → obter JWT (OAuth2PasswordRequestForm)
    POST /api/v1/auth/refresh            → renovar access_token com refresh_token
    POST /api/v1/auth/recuperar-password → enviar email de reset
    POST /api/v1/auth/reset-password     → aplicar nova password com token
    POST /api/v1/auth/alterar-password   → alterar password (autenticado)
    GET  /api/v1/auth/me                 → dados do utilizador atual
    POST /api/v1/auth/desativar          → desativar conta (RGPD)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.utilizador import RoleEnum, Utilizador
from app.services import profile_service
from app.services.auth_service import (
    criar_access_token,
    criar_refresh_token,
    criar_token_reset_db,
    decode_token,
    gerar_reset_token,
    get_current_active_user,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    validar_token_reset_db,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegistarInput(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    nome: str | None = Field(default=None, max_length=255)
    role: RoleEnum = RoleEnum.idoso

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("A password deve conter pelo menos um número.")
        if not any(c.isalpha() for c in v):
            raise ValueError("A password deve conter pelo menos uma letra.")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user_id: str
    role: str


class RefreshInput(BaseModel):
    refresh_token: str


class RecuperarPasswordInput(BaseModel):
    email: EmailStr


class ResetPasswordInput(BaseModel):
    token: str
    nova_password: str = Field(..., min_length=8, max_length=128)


class AlterarPasswordInput(BaseModel):
    password_atual: str
    nova_password: str = Field(..., min_length=8, max_length=128)


class UtilizadorResponse(BaseModel):
    id: str
    email: str
    nome: str | None
    role: str
    is_active: bool
    onboarding_completo: bool
    criado_em: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _enviar_email_reset(email: str, token: str, nome: str | None) -> None:
    """
    Envia email de recuperação de password.
    Usa fastapi-mail via settings.MAIL_*.
    Corre em background para não bloquear a resposta.
    """
    try:
        from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
        from app.core.config import settings

        conf = ConnectionConfig(
            MAIL_USERNAME   = settings.MAIL_USERNAME,
            MAIL_PASSWORD   = settings.MAIL_PASSWORD,
            MAIL_FROM       = settings.MAIL_FROM,
            MAIL_PORT       = settings.MAIL_PORT,
            MAIL_SERVER     = settings.MAIL_SERVER,
            MAIL_STARTTLS   = True,
            MAIL_SSL_TLS    = False,
            USE_CREDENTIALS = True,
        )

        saudacao = f"Olá {nome}," if nome else "Olá,"
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        html = f"""
        <p>{saudacao}</p>
        <p>Recebemos um pedido de recuperação de password para a sua conta no <strong>Memórias Vivas</strong>.</p>
        <p>Clique no botão abaixo para definir uma nova password. O link é válido durante <strong>1 hora</strong>.</p>
        <p><a href="{link}" style="background:#1e3a5f;color:white;padding:12px 24px;
           border-radius:8px;text-decoration:none;font-size:16px;">Recuperar Password</a></p>
        <p>Se não pediu esta recuperação, ignore este email — a sua password não será alterada.</p>
        <p>Equipa Memórias Vivas</p>
        """

        message = MessageSchema(
            subject="Recuperação de Password — Memórias Vivas",
            recipients=[email],
            body=html,
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info("Email de reset enviado para: %s", email)

    except Exception as exc:
        # Falha de email não deve expor informação ao cliente
        logger.exception("Falha ao enviar email de reset: %s", exc)



class PerfilResponse(BaseModel):
    perfil_json: dict | None = Field(default=None)
    temas_explorados: list[str] = Field(default=[])
    atualizado_em: datetime | None = Field(default=None)


# ---------------------------------------------------------------------------
# POST /registar
# ---------------------------------------------------------------------------

@router.post(
    "/registar",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar conta",
)
async def registar(
    payload: RegistarInput,
    db: AsyncSession = Depends(get_db),
):
    """Cria uma nova conta. Devolve JWT para login imediato após registo."""
    email_normalizado = payload.email.lower().strip()

    # Verificar se email já existe
    existente = await get_user_by_email(email_normalizado, db)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta com este email.",
        )

    utilizador = Utilizador(
        email=email_normalizado,
        password_hash=hash_password(payload.password),
        nome=payload.nome,
        role=payload.role,
        is_active=True,
    )
    db.add(utilizador)
    await db.flush()

    user_id = str(utilizador.id)
    logger.info("Novo utilizador registado: %s | role=%s", email_normalizado, payload.role)

    return TokenResponse(
        access_token=criar_access_token(user_id, payload.role.value),
        refresh_token=criar_refresh_token(user_id),
        user_id=user_id,
        role=payload.role.value,
    )


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login — obter JWT",
)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Login com email e password. Compatível com OAuth2PasswordRequestForm
    (campo `username` contém o email — padrão FastAPI/Swagger).
    """
    utilizador = await get_user_by_email(form.username, db)

    if utilizador is None or not verify_password(form.password, utilizador.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou password incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not utilizador.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Contacte o administrador.",
        )

    # Atualizar último login
    utilizador.ultimo_login = datetime.now(timezone.utc)
    await db.flush()

    user_id = str(utilizador.id)
    logger.info("Login: %s | role=%s", utilizador.email, utilizador.role)

    return TokenResponse(
        access_token=criar_access_token(user_id, utilizador.role.value),
        refresh_token=criar_refresh_token(user_id),
        user_id=user_id,
        role=utilizador.role.value,
    )


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token",
)
async def refresh(
    payload: RefreshInput,
    db: AsyncSession = Depends(get_db),
):
    """Troca um refresh_token válido por um novo par de tokens."""
    decoded = decode_token(payload.refresh_token)

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token de refresh inválido.")

    user_id = decoded.get("sub")
    utilizador = await get_user_by_id(user_id, db)

    if utilizador is None or not utilizador.is_active:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado ou inativo.")

    return TokenResponse(
        access_token=criar_access_token(user_id, utilizador.role.value),
        refresh_token=criar_refresh_token(user_id),
        user_id=user_id,
        role=utilizador.role.value,
    )


# ---------------------------------------------------------------------------
# POST /recuperar-password
# ---------------------------------------------------------------------------

@router.post(
    "/recuperar-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicitar recuperação de password por email",
)
async def recuperar_password(
    payload: RecuperarPasswordInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Envia email com link de recuperação.
    Sempre devolve 202 independentemente de o email existir
    — evita enumeração de utilizadores (segurança RGPD).
    """
    utilizador = await get_user_by_email(payload.email, db)

    if utilizador and utilizador.is_active:
        token_plain, token_hash = gerar_reset_token()
        await criar_token_reset_db(utilizador.id, token_hash, db)
        background_tasks.add_task(
            _enviar_email_reset,
            email=utilizador.email,
            token=token_plain,
            nome=utilizador.nome,
        )
        logger.info("Token de reset gerado para: %s", utilizador.email)

    return {"mensagem": "Se o email existir, receberá instruções em breve."}


# ---------------------------------------------------------------------------
# POST /reset-password
# ---------------------------------------------------------------------------

@router.post(
    "/reset-password",
    summary="Aplicar nova password com token de recuperação",
)
async def reset_password(
    payload: ResetPasswordInput,
    db: AsyncSession = Depends(get_db),
):
    """Valida o token de reset e aplica a nova password."""
    token_db = await validar_token_reset_db(payload.token, db)

    utilizador = await get_user_by_id(str(token_db.utilizador_id), db)
    if utilizador is None:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado.")

    utilizador.password_hash = hash_password(payload.nova_password)
    token_db.usado = True
    await db.flush()

    logger.info("Password redefinida para utilizador: %s", utilizador.email)
    return {"mensagem": "Password alterada com sucesso. Pode fazer login."}


# ---------------------------------------------------------------------------
# POST /alterar-password
# ---------------------------------------------------------------------------

@router.post(
    "/alterar-password",
    summary="Alterar password (requer autenticação)",
)
async def alterar_password(
    payload: AlterarPasswordInput,
    current_user: Utilizador = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Altera a password de um utilizador autenticado."""
    if not verify_password(payload.password_atual, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password atual incorreta.",
        )

    current_user.password_hash = hash_password(payload.nova_password)
    await db.flush()

    logger.info("Password alterada: %s", current_user.email)
    return {"mensagem": "Password alterada com sucesso."}


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UtilizadorResponse,
    summary="Dados do utilizador autenticado",
)
async def me(
    current_user: Utilizador = Depends(get_current_active_user),
):
    return UtilizadorResponse(
        id=str(current_user.id),
        email=current_user.email,
        nome=current_user.nome,
        role=current_user.role.value,
        is_active=current_user.is_active,
        onboarding_completo=current_user.onboarding_completo,
        criado_em=current_user.criado_em,
    )



# ---------------------------------------------------------------------------
# GET /perfil
# ---------------------------------------------------------------------------

@router.get(
    "/perfil",
    response_model=PerfilResponse,
    summary="Perfil biográfico do utilizador autenticado",
)
async def get_perfil(
    current_user: Utilizador = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Devolve o perfil biográfico extraído pelo Groq/Gemini."""
    perfil_db = await profile_service.get_profile(str(current_user.id), db)
    if perfil_db is None:
        return PerfilResponse()
    return PerfilResponse(
        perfil_json=perfil_db.perfil_json,
        temas_explorados=list(perfil_db.temas_explorados or []),
        atualizado_em=perfil_db.atualizado_em,
    )


# ---------------------------------------------------------------------------
# POST /desativar
# ---------------------------------------------------------------------------

@router.post(
    "/desativar",
    summary="Desativar conta (RGPD — direito ao esquecimento)",
)
async def desativar_conta(
    current_user: Utilizador = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Desativa a conta sem apagar dados — permite reativação pelo administrador.
    Para apagamento total (RGPD), o administrador executa DELETE em cascata.
    """
    current_user.is_active = False
    await db.flush()
    logger.info("Conta desativada: %s", current_user.email)
    return {"mensagem": "Conta desativada. Os seus dados foram preservados conforme o RGPD."}