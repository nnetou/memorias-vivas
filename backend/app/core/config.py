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
    APP_ENV: str = os.getenv("APP_ENV", "development")
    
    # Base de dados (PostgreSQL async)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Cache de sessão (Redis)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    BACKEND_CORS_ORIGINS: list[str] = ["*"]

settings = Settings()