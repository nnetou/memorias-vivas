"""add_auth_fields_and_reset_tokens

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-04

Adiciona campos de autenticação à tabela utilizadores
e cria a tabela tokens_reset_password.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Criar enum de role
    op.execute("CREATE TYPE role_enum AS ENUM ('administrador', 'cuidador', 'idoso')")

    # Adicionar colunas de autenticação à tabela utilizadores
    op.add_column("utilizadores", sa.Column("email",
        sa.String(255), nullable=True))  # nullable=True primeiro para não falhar em registos existentes
    op.add_column("utilizadores", sa.Column("password_hash",
        sa.Text(), nullable=True))
    op.add_column("utilizadores", sa.Column("role",
        sa.Enum("administrador", "cuidador", "idoso", name="role_enum"),
        nullable=True, server_default="idoso"))
    op.add_column("utilizadores", sa.Column("is_active",
        sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("utilizadores", sa.Column("ultimo_login",
        sa.DateTime(timezone=True), nullable=True))

    # Índice único no email
    op.create_index("idx_utilizadores_email", "utilizadores", ["email"], unique=True)

    # Tornar email e password_hash NOT NULL após adicionar (assume DB limpa em dev)
    op.alter_column("utilizadores", "email", nullable=False)
    op.alter_column("utilizadores", "password_hash", nullable=False)
    op.alter_column("utilizadores", "role", nullable=False)

    # Tabela tokens_reset_password
    op.create_table(
        "tokens_reset_password",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("utilizador_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash",    sa.String(255),     nullable=False, unique=True),
        sa.Column("expira_em",     sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado",         sa.Boolean(),       nullable=False,
                  server_default="false"),
        sa.Column("criado_em",     sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["utilizador_id"], ["utilizadores.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "idx_tokens_reset_hash",
        "tokens_reset_password",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "idx_tokens_reset_utilizador",
        "tokens_reset_password",
        ["utilizador_id"],
    )


def downgrade() -> None:
    op.drop_table("tokens_reset_password")

    op.drop_index("idx_utilizadores_email", table_name="utilizadores")
    op.drop_column("utilizadores", "ultimo_login")
    op.drop_column("utilizadores", "is_active")
    op.drop_column("utilizadores", "role")
    op.drop_column("utilizadores", "password_hash")
    op.drop_column("utilizadores", "email")

    op.execute("DROP TYPE role_enum")