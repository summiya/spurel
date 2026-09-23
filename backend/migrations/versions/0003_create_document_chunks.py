"""Create document_chunks table.

Revision ID: 0003_create_document_chunks
Revises: 0002_create_documents
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_create_document_chunks"
down_revision: str | Sequence[str] | None = "0002_create_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the document_chunks table."""
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "chunk_index >= 0 AND chunk_index < 10000",
            name="ck_document_chunks_index_bounds",
        ),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="ck_document_chunks_offset_order",
        ),
        sa.CheckConstraint(
            "end_offset - start_offset <= 20000",
            name="ck_document_chunks_offset_span",
        ),
        sa.CheckConstraint(
            "char_length(text) > 0 AND char_length(text) <= 20000",
            name="ck_document_chunks_text_length",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_index",
        ),
    )
    op.create_index(
        "ix_document_chunks_document_offsets",
        "document_chunks",
        ["document_id", "start_offset", "end_offset"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the document_chunks table."""
    op.drop_index(
        "ix_document_chunks_document_offsets",
        table_name="document_chunks",
    )
    op.drop_table("document_chunks")
