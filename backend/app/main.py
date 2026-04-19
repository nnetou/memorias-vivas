from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import items, users

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

app.include_router(items.router, prefix="/api/v1/items", tags=["Items"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

# Rota de Health Check (Boa Prática)
@app.get("/health", tags=["Sistema"])
async def health_check():
    """Verifica o estado de saúde da API."""
    return {
        "status": "online",
        "projeto": settings.PROJECT_NAME,
        "versao": settings.VERSION
    }