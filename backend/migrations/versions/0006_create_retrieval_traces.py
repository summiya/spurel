"""Create retrieval trace persistence.

Revision ID: 0006_create_retrieval_traces
Revises: 0005_add_chunk_search_vector
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_create_retrieval_traces"
down_revision: str | Sequence[str] | None = "0005_add_chunk_search_vector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create retrieval trace and ranked result snapshot tables."""
    op.create_table(
        "retrieval_traces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("candidate_k", sa.Integer(), nullable=True),
        sa.Column("rrf_k", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "mode IN ('vector', 'keyword', 'hybrid')",
            name="ck_retrieval_traces_mode",
        ),
        sa.CheckConstraint(
            "char_length(query) > 0 AND char_length(query) <= 8000",
            name="ck_retrieval_traces_query_length",
        ),
        sa.CheckConstraint(
            "top_k >= 1 AND top_k <= 100",
            name="ck_retrieval_traces_top_k",
        ),
        sa.CheckConstraint(
            "duration_ms >= 0",
            name="ck_retrieval_traces_duration",
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
            name="ck_retrieval_traces_hybrid_config",
        ),
        sa.CheckConstraint(
            """
            (
                mode IN ('vector', 'hybrid')
                AND embedding_provider IS NOT NULL
                AND embedding_model IS NOT NULL
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
            name="ck_retrieval_traces_embedding_space",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_traces_knowledge_base_created_id",
        "retrieval_traces",
        ["knowledge_base_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "retrieval_trace_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("cosine_similarity", sa.Float(), nullable=True),
        sa.Column("keyword_score", sa.Float(), nullable=True),
        sa.Column("rrf_score", sa.Float(), nullable=True),
        sa.Column("vector_rank", sa.Integer(), nullable=True),
        sa.Column("keyword_rank", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "rank >= 1 AND rank <= 100",
            name="ck_retrieval_trace_results_rank",
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="ck_retrieval_trace_results_chunk_index",
        ),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="ck_retrieval_trace_results_offsets",
        ),
        sa.CheckConstraint(
            "char_length(text) > 0",
            name="ck_retrieval_trace_results_text",
        ),
        sa.ForeignKeyConstraint(
            ["trace_id"],
            ["retrieval_traces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trace_id",
            "rank",
            name="uq_retrieval_trace_results_trace_rank",
        ),
        sa.UniqueConstraint(
            "trace_id",
            "chunk_id",
            name="uq_retrieval_trace_results_trace_chunk",
        ),
    )
    op.create_index(
        "ix_retrieval_trace_results_trace_rank",
        "retrieval_trace_results",
        ["trace_id", "rank"],
        unique=False,
    )


def downgrade() -> None:
    """Drop retrieval trace persistence."""
    op.drop_index(
        "ix_retrieval_trace_results_trace_rank",
        table_name="retrieval_trace_results",
    )
    op.drop_table("retrieval_trace_results")

    op.drop_index(
        "ix_retrieval_traces_knowledge_base_created_id",
        table_name="retrieval_traces",
    )
    op.drop_table("retrieval_traces")
