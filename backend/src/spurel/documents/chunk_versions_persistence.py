"""Persistence model for immutable document chunk-set version metadata."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from spurel.db import Base


class DocumentChunkVersionRecord(Base):
    """One immutable chunk snapshot for a source document."""

    __tablename__ = "document_chunk_versions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_chunk_versions_version"),
        CheckConstraint(
            "chunk_count >= 1 AND chunk_count <= 10000",
            name="ck_chunk_versions_chunk_count",
        ),
        CheckConstraint(
            "status IN ('processing', 'ready', 'failed')",
            name="ck_chunk_versions_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_chunk_versions_attempt_count"),
        CheckConstraint(
            "(status = 'processing' AND attempt_id IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'processing' AND attempt_id IS NULL AND lease_expires_at IS NULL)",
            name="ck_chunk_versions_attempt_lease",
        ),
        Index(
            "uq_chunk_versions_processing_document",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'processing'"),
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'ready'"))
    attempt_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
