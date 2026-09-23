import asyncio
from uuid import uuid4

import pytest

from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceResult,
    RetrievalTraceValidationError,
)


def _vector_result(*, rank: int = 1, chunk_id=None) -> RetrievalTraceResult:
    return RetrievalTraceResult(
        rank=rank,
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        chunk_index=rank - 1,
        text=f"chunk-{rank}",
        start_offset=(rank - 1) * 10,
        end_offset=((rank - 1) * 10) + 7,
        cosine_similarity=0.9,
    )


def _hybrid_result(*, rank: int = 1) -> RetrievalTraceResult:
    return RetrievalTraceResult(
        rank=rank,
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=rank - 1,
        text=f"chunk-{rank}",
        start_offset=(rank - 1) * 10,
        end_offset=((rank - 1) * 10) + 7,
        cosine_similarity=0.9,
        keyword_score=0.7,
        rrf_score=0.03,
        vector_rank=1,
        keyword_rank=2,
    )


def test_vector_trace_requires_complete_embedding_space() -> None:
    trace = RetrievalTrace.create(
        knowledge_base_id=uuid4(),
        mode=RetrievalTraceMode.VECTOR,
        query="  authentication  ",
        top_k=10,
        duration_ms=12.5,
        embedding_provider="openai",
        embedding_model="text-embedding-example",
        embedding_dimensions=1536,
        results=(_vector_result(),),
    )

    assert trace.query == "authentication"
    assert trace.mode is RetrievalTraceMode.VECTOR
    assert trace.embedding_dimensions == 1536


def test_hybrid_trace_preserves_fusion_configuration() -> None:
    trace = RetrievalTrace.create(
        knowledge_base_id=uuid4(),
        mode=RetrievalTraceMode.HYBRID,
        query="query",
        top_k=10,
        candidate_k=50,
        rrf_k=60,
        duration_ms=20.0,
        embedding_provider="openai",
        embedding_model="model",
        embedding_dimensions=2,
        results=(_hybrid_result(),),
    )

    assert trace.candidate_k == 50
    assert trace.rrf_k == 60
    assert trace.results[0].rrf_score == 0.03


def test_trace_rejects_duplicate_chunks() -> None:
    chunk_id = uuid4()

    with pytest.raises(RetrievalTraceValidationError):
        RetrievalTrace.create(
            knowledge_base_id=uuid4(),
            mode=RetrievalTraceMode.VECTOR,
            query="query",
            top_k=10,
            duration_ms=1.0,
            embedding_provider="openai",
            embedding_model="model",
            embedding_dimensions=2,
            results=(
                _vector_result(rank=1, chunk_id=chunk_id),
                _vector_result(rank=2, chunk_id=chunk_id),
            ),
        )


def test_keyword_trace_rejects_embedding_space_metadata() -> None:
    result = RetrievalTraceResult(
        rank=1,
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text="keyword result",
        start_offset=0,
        end_offset=14,
        keyword_score=0.8,
    )

    with pytest.raises(RetrievalTraceValidationError):
        RetrievalTrace.create(
            knowledge_base_id=uuid4(),
            mode=RetrievalTraceMode.KEYWORD,
            query="query",
            top_k=10,
            duration_ms=1.0,
            embedding_provider="openai",
            embedding_model="model",
            embedding_dimensions=2,
            results=(result,),
        )


class FakeTraceRepository:
    def __init__(self) -> None:
        self.saved: list[RetrievalTrace] = []

    async def add(self, trace: RetrievalTrace) -> None:
        self.saved.append(trace)


def test_trace_service_delegates_to_repository() -> None:
    repository = FakeTraceRepository()
    service = RetrievalTraceService(repository)
    trace = RetrievalTrace.create(
        knowledge_base_id=uuid4(),
        mode=RetrievalTraceMode.VECTOR,
        query="query",
        top_k=10,
        duration_ms=1.0,
        embedding_provider="openai",
        embedding_model="model",
        embedding_dimensions=2,
        results=(_vector_result(),),
    )

    asyncio.run(service.record(trace))

    assert repository.saved == [trace]
