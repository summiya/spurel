"""Persist nullable stage-duration breakdowns without changing historical traces.

Revision ID: 0016_retrieval_stage_timings
Revises: 0015_retrieval_reranking

Existing traces retain NULL (not estimated or backfilled). This migration is
additive, does not rebuild indexes, and does not touch saved evidence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016_retrieval_stage_timings"
down_revision: str | Sequence[str] | None = "0015_retrieval_reranking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "retrieval_traces",
        sa.Column("stage_timings_ms", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("retrieval_traces", "stage_timings_ms")
