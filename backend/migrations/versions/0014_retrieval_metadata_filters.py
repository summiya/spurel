"""Persist the exact metadata filters used for each retrieval trace.

Revision ID: 0014_retrieval_metadata_filters
Revises: 0013_pdf_page_provenance

Additive nullable JSONB; all existing traces remain unfiltered (NULL).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0014_retrieval_metadata_filters"
down_revision: str | Sequence[str] | None = "0013_pdf_page_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist explicit filters for future traces; retain every legacy row."""
    op.add_column(
        "retrieval_traces",
        sa.Column("metadata_filters", JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove only the optional filter snapshot, never trace results."""
    op.drop_column("retrieval_traces", "metadata_filters")
