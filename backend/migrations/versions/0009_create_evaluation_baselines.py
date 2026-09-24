"""Create explicit promoted evaluation baselines.

Revision ID: 0009_create_evaluation_baselines
Revises: 0008_create_evaluation_runs
Create Date: 2026-09-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_create_evaluation_baselines"
down_revision: str | Sequence[str] | None = "0008_create_evaluation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create one promoted baseline per dataset retrieval configuration."""
    op.create_table(
        "evaluation_baselines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "configuration_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("candidate_k", sa.Integer(), nullable=True),
        sa.Column("rrf_k", sa.Integer(), nullable=True),
        sa.Column("embedding_provider", sa.String(length=100), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "mode IN ('vector', 'keyword', 'hybrid')",
            name="ck_evaluation_baselines_mode",
        ),
        sa.CheckConstraint(
            "top_k >= 1 AND top_k <= 100",
            name="ck_evaluation_baselines_top_k",
        ),
        sa.CheckConstraint(
            """
            (
                mode = 'hybrid'
                AND candidate_k IS NOT NULL
                AND candidate_k >= top_k
                AND candidate_k <= 100
                AND rrf_k IS NOT NULL
                AND rrf_k >= 1
                AND rrf_k <= 1000
            )
            OR
            (
                mode <> 'hybrid'
                AND candidate_k IS NULL
                AND rrf_k IS NULL
            )
            """,
            name="ck_evaluation_baselines_hybrid_config",
        ),
        sa.CheckConstraint(
            """
            (
                mode IN ('vector', 'hybrid')
                AND embedding_provider IS NOT NULL
                AND char_length(embedding_provider) > 0
                AND embedding_model IS NOT NULL
                AND char_length(embedding_model) > 0
                AND embedding_dimensions IS NOT NULL
                AND embedding_dimensions > 0
            )
            OR
            (
                mode = 'keyword'
                AND embedding_provider IS NULL
                AND embedding_model IS NULL
                AND embedding_dimensions IS NULL
            )
            """,
            name="ck_evaluation_baselines_embedding_config",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["evaluation_datasets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knowledge_base_id",
            "dataset_id",
            "configuration_fingerprint",
            name="uq_evaluation_baselines_dataset_config",
        ),
    )
    op.create_index(
        "ix_evaluation_baselines_kb_dataset_promoted_id",
        "evaluation_baselines",
        ["knowledge_base_id", "dataset_id", "promoted_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop explicit evaluation baselines."""
    op.drop_index(
        "ix_evaluation_baselines_kb_dataset_promoted_id",
        table_name="evaluation_baselines",
    )
    op.drop_table("evaluation_baselines")
