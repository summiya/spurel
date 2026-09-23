"""Provider-independent vector retrieval values."""

from dataclasses import dataclass
from uuid import UUID

MAX_VECTOR_RETRIEVAL_RESULTS = 100


class VectorRetrievalQueryError(ValueError):
    """Raised when a vector retrieval request is invalid."""


@dataclass(frozen=True, slots=True)
class VectorRetrievalMatch:
    """One ranked chunk returned by vector retrieval."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    cosine_similarity: float
