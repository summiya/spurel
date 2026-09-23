"""Create persisted evaluation benchmark runs.

Revision ID: 0008_create_evaluation_runs
Revises: 0007_create_evaluation_datasets
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_create_evaluation_runs"
down_revision: str | Sequence[str] | None = "0007_create_evaluation_datasets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable evaluation run summaries and per-case snapshots."""
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("candidate_k", sa.Integer(), nullable=True),
        sa.Column("rrf_k", sa.Integer(), nullable=True),
        sa.Column("embedding_provider", sa.String(length=100), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("total_duration_ms", sa.Float(), nullable=False),
        sa.Column("mean_duration_ms", sa.Float(), nullable=False),
        sa.Column("judgment_coverage_case_count", sa.Integer(), nullable=False),
        sa.Column("mean_judgment_coverage_at_k", sa.Float(), nullable=True),
        sa.Column("mean_precision_at_k", sa.Float(), nullable=False),
        sa.Column("mean_recall_at_k", sa.Float(), nullable=False),
        sa.Column("mrr_at_k", sa.Float(), nullable=False),
        sa.Column("mean_ndcg_at_k", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "mode IN ('vector', 'keyword', 'hybrid')",
            name="ck_evaluation_runs_mode",
        ),
        sa.CheckConstraint(
            "top_k >= 1 AND top_k <= 100",
            name="ck_evaluation_runs_top_k",
        ),
        sa.CheckConstraint(
            "case_count >= 1 AND case_count <= 100",
            name="ck_evaluation_runs_case_count",
        ),
        sa.CheckConstraint(
            "judgment_coverage_case_count >= 0 "
            "AND judgment_coverage_case_count <= case_count",
            name="ck_evaluation_runs_coverage_case_count",
        ),
        sa.CheckConstraint(
            "total_duration_ms >= 0 AND mean_duration_ms >= 0",
            name="ck_evaluation_runs_duration",
        ),
        sa.CheckConstraint(
            "mean_judgment_coverage_at_k IS NULL "
            "OR (mean_judgment_coverage_at_k >= 0 "
            "AND mean_judgment_coverage_at_k <= 1)",
            name="ck_evaluation_runs_mean_coverage",
        ),
        sa.CheckConstraint(
            "mean_precision_at_k >= 0 AND mean_precision_at_k <= 1 "
            "AND mean_recall_at_k >= 0 AND mean_recall_at_k <= 1 "
            "AND mrr_at_k >= 0 AND mrr_at_k <= 1 "
            "AND mean_ndcg_at_k >= 0 AND mean_ndcg_at_k <= 1",
            name="ck_evaluation_runs_metrics",
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
            name="ck_evaluation_runs_hybrid_config",
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
            name="ck_evaluation_runs_embedding_config",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_runs_kb_dataset_created_id",
        "evaluation_runs",
        ["knowledge_base_id", "dataset_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "evaluation_run_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("judged_count", sa.Integer(), nullable=False),
        sa.Column("relevant_count", sa.Integer(), nullable=False),
        sa.Column("retrieved_count_at_k", sa.Integer(), nullable=False),
        sa.Column("judged_retrieved_at_k", sa.Integer(), nullable=False),
        sa.Column("relevant_retrieved_at_k", sa.Integer(), nullable=False),
        sa.Column("judgment_coverage_at_k", sa.Float(), nullable=True),
        sa.Column("precision_at_k", sa.Float(), nullable=False),
        sa.Column("recall_at_k", sa.Float(), nullable=False),
        sa.Column("reciprocal_rank_at_k", sa.Float(), nullable=False),
        sa.Column("ndcg_at_k", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "position >= 1 AND position <= 100",
            name="ck_evaluation_run_cases_position",
        ),
        sa.CheckConstraint(
            "char_length(query) > 0 AND char_length(query) <= 8000",
            name="ck_evaluation_run_cases_query",
        ),
        sa.CheckConstraint(
            "duration_ms >= 0",
            name="ck_evaluation_run_cases_duration",
        ),
        sa.CheckConstraint(
            "judged_count >= 1 AND relevant_count >= 1 "
            "AND relevant_count <= judged_count",
            name="ck_evaluation_run_cases_judgments",
        ),
        sa.CheckConstraint(
            "retrieved_count_at_k >= 0 AND retrieved_count_at_k <= 100 "
            "AND judged_retrieved_at_k >= 0 "
            "AND judged_retrieved_at_k <= retrieved_count_at_k "
            "AND relevant_retrieved_at_k >= 0 "
            "AND relevant_retrieved_at_k <= retrieved_count_at_k",
            name="ck_evaluation_run_cases_retrieval_counts",
        ),
        sa.CheckConstraint(
            "judgment_coverage_at_k IS NULL "
            "OR (judgment_coverage_at_k >= 0 AND judgment_coverage_at_k <= 1)",
            name="ck_evaluation_run_cases_coverage",
        ),
        sa.CheckConstraint(
            "precision_at_k >= 0 AND precision_at_k <= 1 "
            "AND recall_at_k >= 0 AND recall_at_k <= 1 "
            "AND reciprocal_rank_at_k >= 0 AND reciprocal_rank_at_k <= 1 "
            "AND ndcg_at_k >= 0 AND ndcg_at_k <= 1",
            name="ck_evaluation_run_cases_metrics",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "position",
            name="uq_evaluation_run_cases_run_position",
        ),
        sa.UniqueConstraint(
            "run_id",
            "case_id",
            name="uq_evaluation_run_cases_run_case",
        ),
    )
    op.create_index(
        "ix_evaluation_run_cases_run_position",
        "evaluation_run_cases",
        ["run_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    """Drop persisted evaluation run history."""
    op.drop_index(
        "ix_evaluation_run_cases_run_position",
        table_name="evaluation_run_cases",
    )
    op.drop_table("evaluation_run_cases")

    op.drop_index(
        "ix_evaluation_runs_kb_dataset_created_id",
        table_name="evaluation_runs",
    )
    op.drop_table("evaluation_runs")
