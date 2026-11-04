"""Keyword retrieval domain values."""

from dataclasses import dataclass
from uuid import UUID

MAX_KEYWORD_RETRIEVAL_RESULTS = 100


class KeywordRetrievalQueryError(ValueError):
    """Raised when a keyword retrieval request is invalid."""


@dataclass(frozen=True, slots=True)
class KeywordRetrievalMatch:
    """One ranked chunk returned by keyword retrieval."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    keyword_score: float
