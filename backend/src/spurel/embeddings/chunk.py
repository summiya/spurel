"""Domain values for persisted chunk embeddings."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from spurel.embeddings.domain import EmbeddingVector, validate_embedding_dimensions

MAX_EMBEDDING_PROVIDER_LENGTH = 64
MAX_EMBEDDING_MODEL_LENGTH = 255


class ChunkEmbeddingMetadataError(ValueError):
    """Raised when chunk embedding metadata is invalid."""


@dataclass(frozen=True, slots=True)
class ChunkEmbedding:
    """One chunk embedding within a named embedding space."""

    chunk_id: UUID
    provider: str
    model: str
    dimensions: int
    vector: EmbeddingVector
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        chunk_id: UUID,
        provider: str,
        model: str,
        vector: EmbeddingVector,
    ) -> "ChunkEmbedding":
        """Create validated chunk embedding metadata."""
        normalized_provider = provider.strip().lower()
        normalized_model = model.strip()
        dimensions = len(vector.values)

        validate_embedding_dimensions(dimensions)

        if not normalized_provider:
            raise ChunkEmbeddingMetadataError(
                "embedding provider must not be empty"
            )
        if len(normalized_provider) > MAX_EMBEDDING_PROVIDER_LENGTH:
            raise ChunkEmbeddingMetadataError(
                "embedding provider identifier is too long"
            )

        if not normalized_model:
            raise ChunkEmbeddingMetadataError(
                "embedding model must not be empty"
            )
        if len(normalized_model) > MAX_EMBEDDING_MODEL_LENGTH:
            raise ChunkEmbeddingMetadataError(
                "embedding model identifier is too long"
            )

        return cls(
            chunk_id=chunk_id,
            provider=normalized_provider,
            model=normalized_model,
            dimensions=dimensions,
            vector=vector,
            created_at=datetime.now(UTC),
        )
