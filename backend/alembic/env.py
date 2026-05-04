from logging.config import fileConfig
import os
import re

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Configuração Alembic
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importa os modelos para que o Alembic os conheça (autogenerate)
from app.models.utilizador import Base
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# URL síncrona para o Alembic
# O Alembic não suporta asyncpg — substitui por psycopg2
# DATABASE_URL no .env usa asyncpg (para o FastAPI); aqui usamos psycopg2
# ---------------------------------------------------------------------------
def get_sync_url() -> str:
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    # postgresql+asyncpg://... → postgresql+psycopg2://...
    url = re.sub(r"postgresql\+asyncpg", "postgresql+psycopg2", url)
    # postgresql://... → postgresql+psycopg2://... (sem driver explícito)
    url = re.sub(r"^postgresql://", "postgresql+psycopg2://", url)
    return url


# ---------------------------------------------------------------------------
# Modo offline — gera SQL sem ligar à DB
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    context.configure(
        url=get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Modo online — liga à DB e aplica as migrações
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_sync_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()