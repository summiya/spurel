"""SP-22 measured, isolated stage timings without fabricated latency stats."""

import asyncio
from uuid import uuid4

import pytest

from spurel.embeddings.domain import EmbeddingBatch
from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.hybrid import HybridRetrievalService
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch
from spurel.retrieval.keyword_service import KeywordRetrievalService
from spurel.retrieval.service import VectorRetrievalService
from spurel.retrieval.timings import capture_stage_timings, time_stage
from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.traced import TracedHybridRetrievalService
from spurel.retrieval.tracing import RetrievalTrace, RetrievalTraceMode, RetrievalTraceValidationError


class EmbeddingProvider:
    provider = "fixture"
    model = "fixture-embedding"
    dimensions = 2

    async def embed(self, texts):
        return EmbeddingBatch.create(
            vectors=[[0.1, 0.2]],
            input_count=len(texts),
            model=self.model,
            dimensions=self.dimensions,
        )


class VectorRepository:
    def __init__(self, chunk_id, doc_id):
        self.chunk_id = chunk_id
        self.doc_id = doc_id

    async def search(self, *, knowledge_base_id, query_vector, provider, model, dimensions, limit):
        return (
            VectorRetrievalMatch(
                chunk_id=self.chunk_id,
                document_id=self.doc_id,
                chunk_index=0,
                text="saved evidence",
                start_offset=0,
                end_offset=14,
                cosine_similarity=0.92,
            ),
        )


class KeywordRepository:
    def __init__(self, chunk_id, doc_id):
        self.chunk_id = chunk_id
        self.doc_id = doc_id

    async def search(self, *, knowledge_base_id, query, limit):
        return (
            KeywordRetrievalMatch(
                chunk_id=self.chunk_id,
                document_id=self.doc_id,
                chunk_index=0,
                text="saved evidence",
                start_offset=0,
                end_offset=14,
                keyword_score=0.35,
            ),
        )


class TraceRepository:
    def __init__(self):
        self.saved = []

    async def add(self, trace):
        self.saved.append(trace)


class Reranker:
    model = "test-local-cross-encoder"

    async def score(self, *, query, documents):
        assert documents == ["saved evidence"]
        return (0.65,)


def _service(trace_repo, reranker=None):
    chunk_id, doc_id = uuid4(), uuid4()
    hybrid = HybridRetrievalService(
        vector_retriever=VectorRetrievalService(
            provider=EmbeddingProvider(),
            repository=VectorRepository(chunk_id, doc_id),
        ),
        keyword_retriever=KeywordRetrievalService(
            KeywordRepository(chunk_id, doc_id)
        ),
    )
    return TracedHybridRetrievalService(
        retriever=hybrid,
        trace_service=RetrievalTraceService(trace_repo),
        embedding_provider="fixture",
        embedding_model="fixture-embedding",
        embedding_dimensions=2,
        reranker=reranker,
    )


def test_real_hybrid_services_measure_all_stages_and_preserve_ranking() -> None:
    repo = TraceRepository()
    service = _service(repo)
    result = asyncio.run(
        service.search(
            knowledge_base_id=uuid4(), query="which", limit=3, candidate_limit=4
        )
    )
    assert len(result.matches) == 1
    assert result.matches[0].rrf_score > 0
    assert set(result.stage_timings_ms) == {
        "query_embedding",
        "vector_search",
        "keyword_search",
        "rrf_fusion",
    }
    assert result.stage_timings_ms == repo.saved[0].stage_timings_ms
    assert all(0 <= value <= result.duration_ms + 1 for value in result.stage_timings_ms.values())
    assert repo.saved[0].reranker_model is None
    assert "cross_encoder" not in result.stage_timings_ms


def test_rerank_stage_only_exists_after_explicit_rerank_call() -> None:
    repo = TraceRepository()
    service = _service(repo, reranker=Reranker())
    result = asyncio.run(
        service.search(
            knowledge_base_id=uuid4(), query="which", limit=1, candidate_limit=4,
            rerank=True,
        )
    )
    assert result.reranker_model == Reranker.model
    assert result.stage_timings_ms["cross_encoder"] >= 0
    assert repo.saved[0].stage_timings_ms == result.stage_timings_ms


def test_context_scoping_prevents_concurrent_request_timing_leaks() -> None:
    async def one(stage):
        with capture_stage_timings() as stages:
            with time_stage(stage):
                await asyncio.sleep(0)
            return dict(stages)

    async def both():
        return await asyncio.gather(one("vector_search"), one("keyword_search"))

    first, second = asyncio.run(both())
    assert set(first) == {"vector_search"}
    assert set(second) == {"keyword_search"}
    with capture_stage_timings() as empty:
        pass
    assert empty == {}


def _create(stage_timings_ms, *, mode=RetrievalTraceMode.KEYWORD, reranker_model=None):
    is_hybrid = mode is RetrievalTraceMode.HYBRID
    return RetrievalTrace.create(
        knowledge_base_id=uuid4(), mode=mode, query="test", top_k=2,
        duration_ms=12.5, results=(),
        candidate_k=4 if is_hybrid else None,
        rrf_k=60 if is_hybrid else None,
        embedding_provider="fixture" if is_hybrid else None,
        embedding_model="fixture-embedding" if is_hybrid else None,
        embedding_dimensions=2 if is_hybrid else None,
        reranker_model=reranker_model,
        stage_timings_ms=stage_timings_ms,
    )


def test_trace_allows_old_null_timing_and_valid_bounded_measurements() -> None:
    assert _create(None).stage_timings_ms is None
    saved = _create({"keyword_search": 4.25})
    assert saved.stage_timings_ms == {"keyword_search": 4.25}
    saved.stage_timings_ms["keyword_search"] = 6.0
    assert saved.stage_timings_ms["keyword_search"] == 6.0


@pytest.mark.parametrize(
    "times",
    [
        {},
        {"unknown": 1.0},
        {"vector_search": 2.0},
        {"keyword_search": -1.0},
        {"keyword_search": float("nan")},
        {"keyword_search": float("inf")},
        {"keyword_search": True},
        {"keyword_search": 14.0},
    ],
)
def test_trace_rejects_unmeasured_or_invalid_stage_data(times) -> None:
    with pytest.raises(RetrievalTraceValidationError):
        _create(times)


def test_trace_rejects_cross_encoder_stage_without_reranking() -> None:
    with pytest.raises(RetrievalTraceValidationError):
        _create({"cross_encoder": 1.0}, mode=RetrievalTraceMode.HYBRID)
    assert _create(
        {"cross_encoder": 1.0}, mode=RetrievalTraceMode.HYBRID,
        reranker_model="test-local-cross-encoder"
    ).stage_timings_ms == {"cross_encoder": 1.0}
