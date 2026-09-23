"""Application service for query embedding and vector retrieval."""

from collections.abc import Sequence
from uuid import UUID

from spurel.embeddings.domain import EmbeddingProvider
from spurel.retrieval.domain import (
    MAX_VECTOR_RETRIEVAL_RESULTS,
    VectorRetrievalMatch,
    VectorRetrievalQueryError,
)
from spurel.retrieval.ports import VectorRetrievalRepository


class VectorRetrievalProviderContractError(RuntimeError):
    """Raised when provider output conflicts with its advertised embedding space."""


class VectorRetrievalService:
    """Embed a query and retrieve matching chunks from one knowledge base."""

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        repository: VectorRetrievalRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int = 10,
    ) -> Sequence[VectorRetrievalMatch]:
        """Run exact cosine retrieval in the provider's embedding space."""
        normalized_query = query.strip()
        if not normalized_query:
            raise VectorRetrievalQueryError("retrieval query must not be empty")

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > MAX_VECTOR_RETRIEVAL_RESULTS
        ):
            raise VectorRetrievalQueryError(
                "retrieval result limit is outside the supported range"
            )

        batch = await self._provider.embed((normalized_query,))

        if batch.model != self._provider.model:
            raise VectorRetrievalProviderContractError(
                "embedding provider returned an unexpected model"
            )

        if batch.dimensions != self._provider.dimensions:
            raise VectorRetrievalProviderContractError(
                "embedding provider returned unexpected dimensions"
            )

        if len(batch.vectors) != 1:
            raise VectorRetrievalProviderContractError(
                "embedding provider returned an unexpected query vector count"
            )

        return await self._repository.search(
            knowledge_base_id=knowledge_base_id,
            query_vector=batch.vectors[0],
            provider=self._provider.provider,
            model=self._provider.model,
            dimensions=self._provider.dimensions,
            limit=limit,
        )
