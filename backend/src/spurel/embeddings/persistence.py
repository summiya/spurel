"""SQLAlchemy persistence model for chunk embeddings."""

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from spurel.db import Base
from spurel.embeddings.chunk import (
    MAX_EMBEDDING_MODEL_LENGTH,
    MAX_EMBEDDING_PROVIDER_LENGTH,
    ChunkEmbedding,
)
from spurel.embeddings.domain import MAX_EMBEDDING_DIMENSIONS, EmbeddingVector


class ChunkEmbeddingRecord(Base):
    """Persisted embedding for one document chunk."""

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        CheckConstraint(
            "char_length(provider) > 0",
            name="ck_chunk_embeddings_provider_not_empty",
        ),
        CheckConstraint(
            "char_length(model) > 0",
            name="ck_chunk_embeddings_model_not_empty",
        ),
        CheckConstraint(
            f"dimensions > 0 AND dimensions <= {MAX_EMBEDDING_DIMENSIONS}",
            name="ck_chunk_embeddings_dimension_bounds",
        ),
        CheckConstraint(
            "vector_dims(embedding) = dimensions",
            name="ck_chunk_embeddings_vector_dimensions",
        ),
        UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            name="uq_chunk_embeddings_chunk_space",
        ),
        Index(
            "ix_chunk_embeddings_space_chunk",
            "provider",
            "model",
            "dimensions",
            "chunk_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    chunk_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(MAX_EMBEDDING_PROVIDER_LENGTH),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(MAX_EMBEDDING_MODEL_LENGTH),
        nullable=False,
    )
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, embedding: ChunkEmbedding) -> "ChunkEmbeddingRecord":
        """Create a persistence record from a chunk embedding."""
        return cls(
            id=uuid4(),
            chunk_id=embedding.chunk_id,
            provider=embedding.provider,
            model=embedding.model,
            dimensions=embedding.dimensions,
            embedding=list(embedding.vector.values),
            created_at=embedding.created_at,
        )

    def to_domain(self) -> ChunkEmbedding:
        """Convert the persistence record back to a domain value."""
        vector = EmbeddingVector.create(
            list(self.embedding),
            expected_dimensions=self.dimensions,
        )
        return ChunkEmbedding(
            chunk_id=self.chunk_id,
            provider=self.provider,
            model=self.model,
            dimensions=self.dimensions,
            vector=vector,
            created_at=self.created_at,
        )
