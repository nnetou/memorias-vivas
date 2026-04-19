import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Memórias Vivas"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Assistente conversacional para Portfólios Sócio-Culturais."
    
    # Busca as chaves que escreveste no ficheiro .env
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

settings = Settings()