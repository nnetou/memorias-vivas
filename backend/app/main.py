from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import chat

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

app.include_router(chat.router,  prefix="/api/v1/chat",  tags=["Chat"])

# Rota de Health Check (Boa Prática)
@app.get("/health", tags=["Sistema"])
async def health_check():
    """Verifica o estado de saúde da API."""
    return {
        "status": "ok",
        "projeto": settings.PROJECT_NAME,
        "versao": settings.VERSION,
        "ambiente": settings.APP_ENV,
        "chaves": {
            "groq": bool(settings.GROQ_API_KEY),
            "google": bool(settings.GOOGLE_API_KEY),
        },
    }