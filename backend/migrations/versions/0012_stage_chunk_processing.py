"""Track staged, ready and failed chunk-set indexing attempts.

Revision ID: 0012_stage_chunk_processing
Revises: 0011_version_document_chunks
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_stage_chunk_processing"
down_revision: str | Sequence[str] | None = "0011_version_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Mark old versions ready; newly staged versions require explicit promotion."""
    op.add_column(
        "document_chunk_versions",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'ready'"),
        ),
    )
    op.add_column(
        "document_chunk_versions",
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "document_chunk_versions",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_chunk_versions",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_chunk_versions_status",
        "document_chunk_versions",
        "status IN ('processing', 'ready', 'failed')",
    )
    op.create_check_constraint(
        "ck_chunk_versions_attempt_count",
        "document_chunk_versions",
        "attempt_count >= 0",
    )
    op.create_check_constraint(
        "ck_chunk_versions_attempt_lease",
        "document_chunk_versions",
        """
        (status = 'processing' AND attempt_id IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR (status <> 'processing' AND attempt_id IS NULL AND lease_expires_at IS NULL)
        """,
    )
    op.create_index(
        "uq_chunk_versions_processing_document",
        "document_chunk_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'processing'"),
    )


def downgrade() -> None:
    """Discard staged/failed version state, restoring SP-04 metadata."""
    op.drop_index(
        "uq_chunk_versions_processing_document",
        table_name="document_chunk_versions",
    )
    op.drop_constraint(
        "ck_chunk_versions_attempt_lease",
        "document_chunk_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_chunk_versions_attempt_count",
        "document_chunk_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_chunk_versions_status",
        "document_chunk_versions",
        type_="check",
    )
    op.drop_column("document_chunk_versions", "attempt_count")
    op.drop_column("document_chunk_versions", "lease_expires_at")
    op.drop_column("document_chunk_versions", "attempt_id")
    op.drop_column("document_chunk_versions", "status")
