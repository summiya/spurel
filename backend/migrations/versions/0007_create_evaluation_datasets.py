"""Create evaluation datasets and persisted relevance judgments.

Revision ID: 0007_create_evaluation_datasets
Revises: 0006_create_retrieval_traces
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_create_evaluation_datasets"
down_revision: str | Sequence[str] | None = "0006_create_retrieval_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reusable evaluation datasets, cases, and judgments."""
    op.create_table(
        "evaluation_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(name) > 0 AND char_length(name) <= 120",
            name="ck_evaluation_datasets_name",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_datasets_knowledge_base_created_id",
        "evaluation_datasets",
        ["knowledge_base_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(query) > 0 AND char_length(query) <= 8000",
            name="ck_evaluation_cases_query",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["evaluation_datasets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_cases_dataset_created_id",
        "evaluation_cases",
        ["dataset_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "evaluation_judgments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("relevance", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "relevance >= 0 AND relevance <= 3",
            name="ck_evaluation_judgments_relevance",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["evaluation_cases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "case_id",
            "chunk_id",
            name="uq_evaluation_judgments_case_chunk",
        ),
    )
    op.create_index(
        "ix_evaluation_judgments_case_id",
        "evaluation_judgments",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop evaluation dataset persistence."""
    op.drop_index(
        "ix_evaluation_judgments_case_id",
        table_name="evaluation_judgments",
    )
    op.drop_table("evaluation_judgments")

    op.drop_index(
        "ix_evaluation_cases_dataset_created_id",
        table_name="evaluation_cases",
    )
    op.drop_table("evaluation_cases")

    op.drop_index(
        "ix_evaluation_datasets_knowledge_base_created_id",
        table_name="evaluation_datasets",
    )
    op.drop_table("evaluation_datasets")
