"""add_full_schema_memorias_vivas

Revision ID: 0001
Revises:
Create Date: 2026-05-04

Cria todas as tabelas do schema inicial:
    - utilizadores
    - perfis_biograficos
    - sessoes
    - consentimentos
    - artefactos

Inclui:
    - Índices GIN em perfil_json e metadata (JSONB)
    - Trigger atualizado_em em utilizadores e perfis_biograficos
    - Cascade DELETE em todas as foreign keys
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── utilizadores ────────────────────────────────────────────────────────
    op.create_table(
        "utilizadores",
        sa.Column("id",                  UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("nome",                sa.String(255),     nullable=True),
        sa.Column("onboarding_completo", sa.Boolean(),       nullable=False,
                  server_default="false"),
        sa.Column("criado_em",           sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("atualizado_em",       sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )

    # ── perfis_biograficos ───────────────────────────────────────────────────
    op.create_table(
        "perfis_biograficos",
        sa.Column("id",                   UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("utilizador_id",        UUID(as_uuid=True), nullable=False),
        sa.Column("perfil_json",          JSONB,              nullable=True),
        sa.Column("temas_explorados",     ARRAY(sa.String()), nullable=False,
                  server_default="{}"),
        sa.Column("historico_onboarding", JSONB,              nullable=True),
        sa.Column("atualizado_em",        sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["utilizador_id"], ["utilizadores.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("utilizador_id", name="uq_perfil_utilizador"),
    )

    op.create_index(
        "idx_perfis_perfil_json",
        "perfis_biograficos",
        ["perfil_json"],
        postgresql_using="gin",
    )

    # ── sessoes ──────────────────────────────────────────────────────────────
    op.create_table(
        "sessoes",
        sa.Column("id",               UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("utilizador_id",    UUID(as_uuid=True), nullable=False),
        sa.Column("session_id_redis", sa.String(100),     nullable=True),
        sa.Column("tema",             sa.String(50),      nullable=True),
        sa.Column("resumo_sessao",    sa.Text(),          nullable=True),
        sa.Column("criada_em",        sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["utilizador_id"], ["utilizadores.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index("idx_sessoes_utilizador", "sessoes", ["utilizador_id"])

    # ── consentimentos ───────────────────────────────────────────────────────
    op.create_table(
        "consentimentos",
        sa.Column("id",                        UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("utilizador_id",             UUID(as_uuid=True), nullable=False),
        sa.Column("autoriza_gravacao_voz",     sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column("autoriza_processamento_ia", sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column("autoriza_geracao_video",    sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column("data_assinatura",           sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["utilizador_id"], ["utilizadores.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index("idx_consentimentos_utilizador", "consentimentos", ["utilizador_id"])

    # ── artefactos ───────────────────────────────────────────────────────────
    op.create_table(
        "artefactos",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("utilizador_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tipo",          sa.String(20),      nullable=False),
        sa.Column("url_ficheiro",  sa.Text(),          nullable=True),
        sa.Column("metadata",      JSONB,              nullable=True),
        sa.Column("gerado_em",     sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["utilizador_id"], ["utilizadores.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "idx_artefactos_metadata",
        "artefactos",
        ["metadata"],
        postgresql_using="gin",
    )

    op.create_index("idx_artefactos_utilizador", "artefactos", ["utilizador_id"])

    # ── Função e triggers atualizado_em ──────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_atualizado_em()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.atualizado_em = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER set_atualizado_em_utilizadores
        BEFORE UPDATE ON utilizadores
        FOR EACH ROW EXECUTE FUNCTION trigger_atualizado_em();
    """)

    op.execute("""
        CREATE TRIGGER set_atualizado_em_perfis
        BEFORE UPDATE ON perfis_biograficos
        FOR EACH ROW EXECUTE FUNCTION trigger_atualizado_em();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS set_atualizado_em_perfis      ON perfis_biograficos;")
    op.execute("DROP TRIGGER IF EXISTS set_atualizado_em_utilizadores ON utilizadores;")
    op.execute("DROP FUNCTION IF EXISTS trigger_atualizado_em();")

    op.drop_table("artefactos")
    op.drop_table("consentimentos")
    op.drop_table("sessoes")
    op.drop_table("perfis_biograficos")
    op.drop_table("utilizadores")