"""Add nullable cross-encoder reranking provenance to immutable retrieval traces.

Revision ID: 0015_retrieval_reranking
Revises: 0014_retrieval_metadata_filters

No existing trace, index, source, result, or model is modified or removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_retrieval_reranking"
down_revision: str | Sequence[str] | None = "0014_retrieval_metadata_filters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("retrieval_traces", sa.Column("reranker_model", sa.String(255), nullable=True))
    op.add_column("retrieval_trace_results", sa.Column("candidate_rank", sa.Integer(), nullable=True))
    op.add_column("retrieval_trace_results", sa.Column("rerank_rank", sa.Integer(), nullable=True))
    op.add_column("retrieval_trace_results", sa.Column("rerank_score", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_retrieval_trace_results_rerank",
        "retrieval_trace_results",
        "(candidate_rank IS NULL AND rerank_rank IS NULL AND rerank_score IS NULL) "
        "OR (candidate_rank BETWEEN 1 AND 100 AND rerank_rank BETWEEN 1 AND 100 "
        "AND rerank_rank = rank AND rerank_score IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_retrieval_trace_results_rerank", "retrieval_trace_results", type_="check")
    op.drop_column("retrieval_trace_results", "rerank_score")
    op.drop_column("retrieval_trace_results", "rerank_rank")
    op.drop_column("retrieval_trace_results", "candidate_rank")
    op.drop_column("retrieval_traces", "reranker_model")
