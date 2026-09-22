"""Create documents table.

Revision ID: 0002_create_documents
Revises: 0001_create_knowledge_bases
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_create_documents"
down_revision: str | Sequence[str] | None = "0001_create_knowledge_bases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the documents table."""
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 26214400",
            name="ck_documents_size_bytes_bounds",
        ),
        sa.CheckConstraint(
            "media_type IN ('application/pdf', 'text/markdown', 'text/plain')",
            name="ck_documents_supported_media_type",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documents_knowledge_base_created_id",
        "documents",
        ["knowledge_base_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the documents table."""
    op.drop_index(
        "ix_documents_knowledge_base_created_id",
        table_name="documents",
    )
    op.drop_table("documents")
