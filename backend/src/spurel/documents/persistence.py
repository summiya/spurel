"""SQLAlchemy persistence model for documents."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from spurel.db import Base
from spurel.documents.domain import (
    MAX_DOCUMENT_SIZE_BYTES,
    Document,
    DocumentMediaType,
)


class DocumentRecord(Base):
    """Persisted representation of document metadata."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            f"size_bytes > 0 AND size_bytes <= {MAX_DOCUMENT_SIZE_BYTES}",
            name="ck_documents_size_bytes_bounds",
        ),
        CheckConstraint(
            "media_type IN ('application/pdf', 'text/markdown', 'text/plain')",
            name="ck_documents_supported_media_type",
        ),
        Index(
            "ix_documents_knowledge_base_created_id",
            "knowledge_base_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, document: Document) -> "DocumentRecord":
        """Create a persistence record from a domain entity."""
        return cls(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            filename=document.filename,
            media_type=document.media_type.value,
            size_bytes=document.size_bytes,
            created_at=document.created_at,
        )

    def to_domain(self) -> Document:
        """Convert the persistence record back to a domain entity."""
        return Document(
            id=self.id,
            knowledge_base_id=self.knowledge_base_id,
            filename=self.filename,
            media_type=DocumentMediaType.parse(self.media_type),
            size_bytes=self.size_bytes,
            created_at=self.created_at,
        )
