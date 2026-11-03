"""Store optional immutable PDF page numbers and OCR use per chunk.

Revision ID: 0013_pdf_page_provenance
Revises: 0012_stage_chunk_processing
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_pdf_page_provenance"
down_revision: str | Sequence[str] | None = "0012_stage_chunk_processing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable provenance to existing rows without modifying their index state."""
    op.add_column(
        "document_chunks", sa.Column("page_start", sa.Integer(), nullable=True)
    )
    op.add_column(
        "document_chunks", sa.Column("page_end", sa.Integer(), nullable=True)
    )
    op.add_column(
        "document_chunks",
        sa.Column("ocr_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_document_chunks_pdf_page_range",
        "document_chunks",
        "(page_start IS NULL AND page_end IS NULL) "
        "OR (page_start >= 1 AND page_end >= page_start)",
    )
    op.create_check_constraint(
        "ck_document_chunks_ocr_has_page",
        "document_chunks",
        "NOT ocr_used OR page_start IS NOT NULL",
    )


def downgrade() -> None:
    """Undo only the optional SP-18 metadata columns (not document versions)."""
    op.drop_constraint(
        "ck_document_chunks_ocr_has_page", "document_chunks", type_="check"
    )
    op.drop_constraint(
        "ck_document_chunks_pdf_page_range", "document_chunks", type_="check"
    )
    op.drop_column("document_chunks", "ocr_used")
    op.drop_column("document_chunks", "page_end")
    op.drop_column("document_chunks", "page_start")
