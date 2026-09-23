"""Application service for keyword retrieval."""

from collections.abc import Sequence
from uuid import UUID

from spurel.retrieval.keyword_domain import (
    MAX_KEYWORD_RETRIEVAL_RESULTS,
    KeywordRetrievalMatch,
    KeywordRetrievalQueryError,
)
from spurel.retrieval.keyword_ports import KeywordRetrievalRepository


class KeywordRetrievalService:
    """Retrieve lexical chunk matches from one knowledge base."""

    def __init__(self, repository: KeywordRetrievalRepository) -> None:
        self._repository = repository

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int = 10,
    ) -> Sequence[KeywordRetrievalMatch]:
        """Run bounded lexical retrieval."""
        normalized_query = query.strip()
        if not normalized_query:
            raise KeywordRetrievalQueryError(
                "keyword retrieval query must not be empty"
            )

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > MAX_KEYWORD_RETRIEVAL_RESULTS
        ):
            raise KeywordRetrievalQueryError(
                "keyword retrieval result limit is outside the supported range"
            )

        return await self._repository.search(
            knowledge_base_id=knowledge_base_id,
            query=normalized_query,
            limit=limit,
        )
