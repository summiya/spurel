"""Application-facing persistence port for keyword retrieval."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from spurel.retrieval.keyword_domain import KeywordRetrievalMatch


class KeywordRetrievalRepositoryError(RuntimeError):
    """Raised when keyword retrieval persistence cannot complete."""


class KeywordRetrievalRepository(Protocol):
    """Search persisted chunks using lexical full-text retrieval."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        """Return ranked keyword matches for one knowledge base."""
        ...
