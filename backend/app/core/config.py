import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Memórias Vivas"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Assistente conversacional para Portfólios Sócio-Culturais."

    # Chaves de API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # Base de dados (PostgreSQL async)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Cache de sessão (Redis)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    # JWT — Autenticação
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # Email — Recuperação de password
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", "587"))
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "smtp.gmail.com")

    # Frontend — link no email de reset
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")


settings = Settings()