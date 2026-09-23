"""SQLAlchemy persistence model for document chunks."""

from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from spurel.db import Base
from spurel.documents.chunking import (
    MAX_CHUNKS_PER_DOCUMENT,
    MAX_CHUNK_SIZE_CHARACTERS,
    DocumentChunk,
)


class DocumentChunkRecord(Base):
    """Persisted representation of one deterministic document chunk."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint(
            f"chunk_index >= 0 AND chunk_index < {MAX_CHUNKS_PER_DOCUMENT}",
            name="ck_document_chunks_index_bounds",
        ),
        CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="ck_document_chunks_offset_order",
        ),
        CheckConstraint(
            f"end_offset - start_offset <= {MAX_CHUNK_SIZE_CHARACTERS}",
            name="ck_document_chunks_offset_span",
        ),
        CheckConstraint(
            f"char_length(text) > 0 AND char_length(text) <= {MAX_CHUNK_SIZE_CHARACTERS}",
            name="ck_document_chunks_text_length",
        ),
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_index",
        ),
        Index(
            "ix_document_chunks_document_offsets",
            "document_id",
            "start_offset",
            "end_offset",
        ),
        Index(
            "ix_document_chunks_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english'::regconfig, text)",
            persisted=True,
        ),
        nullable=False,
    )
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    @classmethod
    def from_domain(
        cls,
        *,
        document_id: UUID,
        chunk: DocumentChunk,
    ) -> "DocumentChunkRecord":
        """Create a persistence record from a chunking result."""
        return cls(
            id=uuid4(),
            document_id=document_id,
            chunk_index=chunk.index,
            text=chunk.text,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
        )

    def to_domain(self) -> DocumentChunk:
        """Convert the persistence record back to a chunk value."""
        return DocumentChunk(
            index=self.chunk_index,
            text=self.text,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
        )
