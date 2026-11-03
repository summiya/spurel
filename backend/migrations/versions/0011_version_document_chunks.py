"""Preserve immutable chunk-set versions and activate one version per document.

Revision ID: 0011_version_document_chunks
Revises: 0010_create_evaluation_baseline_promotions
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_version_document_chunks"
down_revision: str | Sequence[str] | None = "0010_create_evaluation_baseline_promotions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill existing chunk identities into version one without rewriting them."""
    op.add_column(
        "documents",
        sa.Column(
            "active_chunk_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_documents_active_chunk_version",
        "documents",
        "active_chunk_version >= 0",
    )

    op.create_table(
        "document_chunk_versions",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_chunk_versions_version"),
        sa.CheckConstraint(
            "chunk_count >= 1 AND chunk_count <= 10000",
            name="ck_chunk_versions_chunk_count",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "version"),
    )
    # Existing chunks retain their original UUIDs, embeddings, and judgments.
    op.execute(
        """
        INSERT INTO document_chunk_versions (document_id, version, chunk_count, created_at)
        SELECT document_id, 1, COUNT(*)::integer, CURRENT_TIMESTAMP
        FROM document_chunks
        GROUP BY document_id
        """
    )
    op.execute(
        """
        UPDATE documents
        SET active_chunk_version = 1
        WHERE id IN (SELECT document_id FROM document_chunk_versions)
        """
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "chunk_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_check_constraint(
        "ck_document_chunks_version",
        "document_chunks",
        "chunk_version >= 1",
    )
    op.drop_constraint(
        "uq_document_chunks_document_index",
        "document_chunks",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_document_chunks_document_version_index",
        "document_chunks",
        ["document_id", "chunk_version", "chunk_index"],
    )
    op.create_foreign_key(
        "fk_document_chunks_version",
        "document_chunks",
        "document_chunk_versions",
        ["document_id", "chunk_version"],
        ["document_id", "version"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Restore the one-set schema; discard non-active historical chunk versions.

    This downgrade is intentionally lossy. Back up historical chunks and embeddings
    before downgrading a database that contains multiple versions.
    """
    op.execute(
        """
        DELETE FROM document_chunks AS chunk
        USING documents AS document
        WHERE chunk.document_id = document.id
          AND chunk.chunk_version <> document.active_chunk_version
        """
    )
    op.drop_constraint("fk_document_chunks_version", "document_chunks", type_="foreignkey")
    op.drop_constraint(
        "uq_document_chunks_document_version_index",
        "document_chunks",
        type_="unique",
    )
    op.drop_constraint("ck_document_chunks_version", "document_chunks", type_="check")
    op.drop_column("document_chunks", "chunk_version")
    op.create_unique_constraint(
        "uq_document_chunks_document_index",
        "document_chunks",
        ["document_id", "chunk_index"],
    )
    op.drop_table("document_chunk_versions")
    op.drop_constraint("ck_documents_active_chunk_version", "documents", type_="check")
    op.drop_column("documents", "active_chunk_version")
