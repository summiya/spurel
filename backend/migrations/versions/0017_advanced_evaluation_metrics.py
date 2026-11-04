"""Nullable Hit@K and AP/MAP@K snapshots with Wilson reporting intervals.

Revision ID: 0017_advanced_evaluation_metrics
Revises: 0016_retrieval_stage_timings

Historical evaluation runs and cases stay NULL. There is no inference,
automatic benchmark run, index rebuild or data backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_advanced_evaluation_metrics"
down_revision: str | Sequence[str] | None = "0016_retrieval_stage_timings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in (
        "hit_rate_at_k",
        "mean_average_precision_at_k",
        "hit_rate_wilson_95_lower",
        "hit_rate_wilson_95_upper",
    ):
        op.add_column("evaluation_runs", sa.Column(name, sa.Float(), nullable=True))
    op.add_column("evaluation_run_cases", sa.Column("hit_at_k", sa.Boolean(), nullable=True))
    op.add_column(
        "evaluation_run_cases", sa.Column("average_precision_at_k", sa.Float(), nullable=True)
    )
    op.create_check_constraint(
        "ck_evaluation_runs_extended_metrics",
        "evaluation_runs",
        "(hit_rate_at_k IS NULL OR hit_rate_at_k BETWEEN 0 AND 1) "
        "AND (mean_average_precision_at_k IS NULL "
        "OR mean_average_precision_at_k BETWEEN 0 AND 1) "
        "AND (hit_rate_wilson_95_lower IS NULL OR hit_rate_wilson_95_lower BETWEEN 0 AND 1) "
        "AND (hit_rate_wilson_95_upper IS NULL OR hit_rate_wilson_95_upper BETWEEN 0 AND 1) "
        "AND ((hit_rate_wilson_95_lower IS NULL AND hit_rate_wilson_95_upper IS NULL) "
        "OR hit_rate_wilson_95_lower <= hit_rate_wilson_95_upper)",
    )
    op.create_check_constraint(
        "ck_evaluation_run_cases_average_precision",
        "evaluation_run_cases",
        "average_precision_at_k IS NULL OR average_precision_at_k BETWEEN 0 AND 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_evaluation_run_cases_average_precision", "evaluation_run_cases", type_="check"
    )
    op.drop_constraint("ck_evaluation_runs_extended_metrics", "evaluation_runs", type_="check")
    op.drop_column("evaluation_run_cases", "average_precision_at_k")
    op.drop_column("evaluation_run_cases", "hit_at_k")
    for name in (
        "hit_rate_wilson_95_upper",
        "hit_rate_wilson_95_lower",
        "mean_average_precision_at_k",
        "hit_rate_at_k",
    ):
        op.drop_column("evaluation_runs", name)
