"""Create chunk_embeddings table.

Revision ID: 0004_create_chunk_embeddings
Revises: 0003_create_document_chunks
Create Date: 2026-09-23
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa

revision: str = "0004_create_chunk_embeddings"
down_revision: str | Sequence[str] | None = "0003_create_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable pgvector and create the chunk_embeddings table."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(provider) > 0",
            name="ck_chunk_embeddings_provider_not_empty",
        ),
        sa.CheckConstraint(
            "char_length(model) > 0",
            name="ck_chunk_embeddings_model_not_empty",
        ),
        sa.CheckConstraint(
            "dimensions > 0 AND dimensions <= 16384",
            name="ck_chunk_embeddings_dimension_bounds",
        ),
        sa.CheckConstraint(
            "vector_dims(embedding) = dimensions",
            name="ck_chunk_embeddings_vector_dimensions",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            name="uq_chunk_embeddings_chunk_space",
        ),
    )
    op.create_index(
        "ix_chunk_embeddings_space_chunk",
        "chunk_embeddings",
        ["provider", "model", "dimensions", "chunk_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the chunk_embeddings table."""
    op.drop_index(
        "ix_chunk_embeddings_space_chunk",
        table_name="chunk_embeddings",
    )
    op.drop_table("chunk_embeddings")
