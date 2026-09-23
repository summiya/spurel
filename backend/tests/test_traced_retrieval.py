import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.hybrid import HybridRetrievalMatch
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch
from spurel.retrieval.trace_ports import RetrievalTracePersistenceError
from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.traced import (
    TracedHybridRetrievalService,
    TracedKeywordRetrievalService,
    TracedVectorRetrievalService,
)
from spurel.retrieval.tracing import RetrievalTrace, RetrievalTraceMode


class FakeTraceRepository:
    def __init__(self) -> None:
        self.saved: list[RetrievalTrace] = []
        self.fail = False

    async def add(self, trace: RetrievalTrace) -> None:
        if self.fail:
            raise RetrievalTracePersistenceError("trace database details")
        self.saved.append(trace)


class FakeVectorRetriever:
    def __init__(self, results: Sequence[VectorRetrievalMatch]) -> None:
        self.results = tuple(results)

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        return self.results[:limit]


class FakeKeywordRetriever:
    def __init__(self, results: Sequence[KeywordRetrievalMatch]) -> None:
        self.results = tuple(results)

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        return self.results[:limit]


class FakeHybridRetriever:
    def __init__(self, results: Sequence[HybridRetrievalMatch]) -> None:
        self.results = tuple(results)

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
        candidate_limit: int,
        rrf_k: int,
    ) -> Sequence[HybridRetrievalMatch]:
        return self.results[:limit]


def test_traced_vector_search_persists_exact_ranked_snapshot() -> None:
    knowledge_base_id = uuid4()
    match = VectorRetrievalMatch(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=2,
        text="vector result",
        start_offset=20,
        end_offset=33,
        cosine_similarity=0.93,
    )
    repository = FakeTraceRepository()
    service = TracedVectorRetrievalService(
        retriever=FakeVectorRetriever((match,)),  # type: ignore[arg-type]
        trace_service=RetrievalTraceService(repository),
        embedding_provider="openai",
        embedding_model="text-embedding-example",
        embedding_dimensions=1536,
    )

    result = asyncio.run(
        service.search(
            knowledge_base_id=knowledge_base_id,
            query="  architecture  ",
            limit=5,
        )
    )

    assert result.matches == (match,)
    assert result.duration_ms >= 0
    assert len(repository.saved) == 1

    trace = repository.saved[0]
    assert result.trace_id == trace.id
    assert trace.knowledge_base_id == knowledge_base_id
    assert trace.mode is RetrievalTraceMode.VECTOR
    assert trace.query == "architecture"
    assert trace.top_k == 5
    assert trace.embedding_provider == "openai"
    assert trace.embedding_model == "text-embedding-example"
    assert trace.embedding_dimensions == 1536
    assert trace.duration_ms == result.duration_ms
    assert trace.results[0].rank == 1
    assert trace.results[0].chunk_id == match.chunk_id
    assert trace.results[0].cosine_similarity == 0.93


def test_traced_keyword_search_persists_keyword_score() -> None:
    match = KeywordRetrievalMatch(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=1,
        text="keyword result",
        start_offset=10,
        end_offset=24,
        keyword_score=0.71,
    )
    repository = FakeTraceRepository()
    service = TracedKeywordRetrievalService(
        retriever=FakeKeywordRetriever((match,)),  # type: ignore[arg-type]
        trace_service=RetrievalTraceService(repository),
    )

    result = asyncio.run(
        service.search(
            knowledge_base_id=uuid4(),
            query="keyword",
            limit=10,
        )
    )

    trace = repository.saved[0]
    assert result.trace_id == trace.id
    assert trace.mode is RetrievalTraceMode.KEYWORD
    assert trace.embedding_provider is None
    assert trace.results[0].keyword_score == 0.71


def test_traced_hybrid_search_persists_fusion_configuration_and_source_ranks() -> None:
    match = HybridRetrievalMatch(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=3,
        text="hybrid result",
        start_offset=30,
        end_offset=43,
        rrf_score=0.0325,
        vector_rank=1,
        keyword_rank=2,
        cosine_similarity=0.91,
        keyword_score=0.75,
    )
    repository = FakeTraceRepository()
    service = TracedHybridRetrievalService(
        retriever=FakeHybridRetriever((match,)),  # type: ignore[arg-type]
        trace_service=RetrievalTraceService(repository),
        embedding_provider="openai",
        embedding_model="text-embedding-example",
        embedding_dimensions=1536,
    )

    result = asyncio.run(
        service.search(
            knowledge_base_id=uuid4(),
            query="hybrid query",
            limit=10,
            candidate_limit=50,
            rrf_k=60,
        )
    )

    trace = repository.saved[0]
    assert result.trace_id == trace.id
    assert trace.mode is RetrievalTraceMode.HYBRID
    assert trace.candidate_k == 50
    assert trace.rrf_k == 60
    assert trace.results[0].rrf_score == 0.0325
    assert trace.results[0].vector_rank == 1
    assert trace.results[0].keyword_rank == 2


def test_trace_persistence_failure_prevents_successful_traced_result() -> None:
    match = VectorRetrievalMatch(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text="result",
        start_offset=0,
        end_offset=6,
        cosine_similarity=0.9,
    )
    repository = FakeTraceRepository()
    repository.fail = True
    service = TracedVectorRetrievalService(
        retriever=FakeVectorRetriever((match,)),  # type: ignore[arg-type]
        trace_service=RetrievalTraceService(repository),
        embedding_provider="openai",
        embedding_model="model",
        embedding_dimensions=2,
    )

    with pytest.raises(RetrievalTracePersistenceError):
        asyncio.run(
            service.search(
                knowledge_base_id=uuid4(),
                query="query",
                limit=10,
            )
        )
