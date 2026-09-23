import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.embeddings.domain import EmbeddingBatch, EmbeddingVector
from spurel.retrieval.domain import VectorRetrievalMatch, VectorRetrievalQueryError
from spurel.retrieval.service import (
    VectorRetrievalProviderContractError,
    VectorRetrievalService,
)


class FakeEmbeddingProvider:
    provider = "test-provider"
    model = "test-model"
    dimensions = 2

    def __init__(self) -> None:
        self.queries: list[tuple[str, ...]] = []
        self.override_model: str | None = None
        self.override_dimensions: int | None = None

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self.queries.append(tuple(texts))
        model = self.override_model or self.model
        dimensions = self.override_dimensions or self.dimensions
        return EmbeddingBatch.create(
            vectors=[[0.1] * dimensions],
            input_count=1,
            model=model,
            dimensions=dimensions,
        )


class FakeVectorRetrievalRepository:
    def __init__(self) -> None:
        self.last_call: dict[str, object] | None = None
        self.results: tuple[VectorRetrievalMatch, ...] = ()

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query_vector: EmbeddingVector,
        provider: str,
        model: str,
        dimensions: int,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "query_vector": query_vector,
            "provider": provider,
            "model": model,
            "dimensions": dimensions,
            "limit": limit,
        }
        return self.results


def test_search_embeds_query_and_scopes_repository_call() -> None:
    knowledge_base_id = uuid4()
    chunk_id = uuid4()
    document_id = uuid4()
    provider = FakeEmbeddingProvider()
    repository = FakeVectorRetrievalRepository()
    repository.results = (
        VectorRetrievalMatch(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=0,
            text="retrieved context",
            start_offset=0,
            end_offset=17,
            cosine_similarity=0.91,
        ),
    )
    service = VectorRetrievalService(
        provider=provider,
        repository=repository,
    )

    result = asyncio.run(
        service.search(
            knowledge_base_id=knowledge_base_id,
            query="  architecture  ",
            limit=5,
        )
    )

    assert provider.queries == [("architecture",)]
    assert tuple(result) == repository.results
    assert repository.last_call is not None
    assert repository.last_call["knowledge_base_id"] == knowledge_base_id
    assert repository.last_call["provider"] == "test-provider"
    assert repository.last_call["model"] == "test-model"
    assert repository.last_call["dimensions"] == 2
    assert repository.last_call["limit"] == 5


@pytest.mark.parametrize(
    ("query", "limit"),
    [
        ("", 10),
        ("   ", 10),
        ("query", 0),
        ("query", 101),
        ("query", True),
    ],
)
def test_search_rejects_invalid_query_or_limit(query: str, limit: int) -> None:
    service = VectorRetrievalService(
        provider=FakeEmbeddingProvider(),
        repository=FakeVectorRetrievalRepository(),
    )

    with pytest.raises(VectorRetrievalQueryError):
        asyncio.run(
            service.search(
                knowledge_base_id=uuid4(),
                query=query,
                limit=limit,
            )
        )


def test_search_rejects_provider_model_contract_mismatch() -> None:
    provider = FakeEmbeddingProvider()
    provider.override_model = "unexpected-model"
    repository = FakeVectorRetrievalRepository()
    service = VectorRetrievalService(provider=provider, repository=repository)

    with pytest.raises(VectorRetrievalProviderContractError):
        asyncio.run(
            service.search(
                knowledge_base_id=uuid4(),
                query="query",
            )
        )

    assert repository.last_call is None


def test_search_rejects_provider_dimension_contract_mismatch() -> None:
    provider = FakeEmbeddingProvider()
    provider.override_dimensions = 3
    repository = FakeVectorRetrievalRepository()
    service = VectorRetrievalService(provider=provider, repository=repository)

    with pytest.raises(VectorRetrievalProviderContractError):
        asyncio.run(
            service.search(
                knowledge_base_id=uuid4(),
                query="query",
            )
        )

    assert repository.last_call is None
