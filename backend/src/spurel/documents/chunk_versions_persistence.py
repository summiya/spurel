"""Persistence model for immutable document chunk-set version metadata."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Uuid
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
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
