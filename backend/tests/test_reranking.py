"""SP-21: explicit reranking preserves source provenance and fails closed."""

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from spurel.retrieval.hybrid import HybridRetrievalMatch
from spurel.retrieval.reranking import (
    HttpCrossEncoderReranker,
    RerankerUnavailableError,
    rerank_hybrid_matches,
)
from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.traced import TracedHybridRetrievalService
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceValidationError,
)


def _match(rank: int) -> HybridRetrievalMatch:
    return HybridRetrievalMatch(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=rank,
        text=f"candidate text {rank}",
        start_offset=rank * 20,
        end_offset=rank * 20 + 16,
        rrf_score=0.04 - rank * 0.001,
        vector_rank=rank,
        keyword_rank=None,
        cosine_similarity=0.9,
        keyword_score=None,
    )


class FakeReranker:
    model = "test-cross-encoder"

    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[str]]] = []

    async def score(self, *, query: str, documents: list[str]) -> list[float]:
        self.calls.append((query, list(documents)))
        return self.scores


def test_rerank_can_promote_last_candidate_without_changing_original_scores() -> None:
    candidates = [_match(1), _match(2), _match(3)]
    adapter = FakeReranker([0.1, 0.6, 0.9])
    ranked = asyncio.run(
        rerank_hybrid_matches(reranker=adapter, query="question", candidates=candidates, top_k=2)
    )
    assert adapter.calls == [("question", [item.text for item in candidates])]
    assert [item.chunk_id for item in ranked] == [candidates[2].chunk_id, candidates[1].chunk_id]
    assert [item.candidate_rank for item in ranked] == [3, 2]
    assert [item.rerank_rank for item in ranked] == [1, 2]
    assert [item.rerank_score for item in ranked] == [0.9, 0.6]
    assert ranked[0].rrf_score == candidates[2].rrf_score
    assert ranked[0].vector_rank == candidates[2].vector_rank


@pytest.mark.parametrize("scores", [[0.1], [float("nan"), 1.0], [True, 1.0]])
def test_reranker_rejects_missing_nonfinite_or_boolean_scores(scores: list[float]) -> None:
    with pytest.raises(RerankerUnavailableError):
        asyncio.run(
            rerank_hybrid_matches(
                reranker=FakeReranker(scores),
                query="question",
                candidates=[_match(1), _match(2)],
                top_k=2,
            )
        )


def test_rerank_ties_preserve_initial_rrf_rank() -> None:
    candidates = [_match(1), _match(2)]
    ranked = asyncio.run(
        rerank_hybrid_matches(
            reranker=FakeReranker([0.3, 0.3]), query="q", candidates=candidates, top_k=2
        )
    )
    assert [item.chunk_id for item in ranked] == [item.chunk_id for item in candidates]


def test_misconfigured_reranker_fails_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPUREL_RERANKER_URL", raising=False)
    monkeypatch.delenv("SPUREL_RERANKER_MODEL", raising=False)
    with pytest.raises(RerankerUnavailableError):
        HttpCrossEncoderReranker.from_env()
    with pytest.raises(RerankerUnavailableError):
        HttpCrossEncoderReranker(url="file:///tmp/secret", model="bad")
    with pytest.raises(RerankerUnavailableError):
        HttpCrossEncoderReranker(url="http://secret:pass@localhost:99/rerank", model="bad")


class FakeRetriever:
    def __init__(self, matches: list[HybridRetrievalMatch]) -> None:
        self.matches = matches
        self.limits: list[int] = []

    async def search(self, *, knowledge_base_id, query, limit, candidate_limit, rrf_k):
        self.limits.append(limit)
        return tuple(self.matches[:limit])


class TraceRepo:
    def __init__(self) -> None:
        self.saved: list[RetrievalTrace] = []

    async def add(self, trace: RetrievalTrace) -> None:
        self.saved.append(trace)


def test_explicit_rerank_fetches_candidate_pool_and_persists_provenance() -> None:
    candidates = [_match(1), _match(2), _match(3)]
    retriever, adapter, repo = FakeRetriever(candidates), FakeReranker([0.2, 0.4, 0.8]), TraceRepo()
    service = TracedHybridRetrievalService(
        retriever=retriever,
        trace_service=RetrievalTraceService(repo),
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        reranker=adapter,
    )
    run = asyncio.run(
        service.search(
            knowledge_base_id=uuid4(),
            query="question",
            limit=2,
            candidate_limit=3,
            rrf_k=60,
            rerank=True,
        )
    )
    assert retriever.limits == [3]
    assert run.reranker_model == adapter.model
    assert len(run.matches) == 2
    trace = repo.saved[0]
    assert trace.mode == RetrievalTraceMode.HYBRID
    assert trace.reranker_model == adapter.model
    assert trace.results[0].candidate_rank == 3
    assert trace.results[0].rerank_rank == 1
    assert trace.results[0].rerank_score == 0.8

    plain = asyncio.run(
        service.search(
            knowledge_base_id=uuid4(), query="question", limit=2, candidate_limit=3, rrf_k=60
        )
    )
    assert retriever.limits == [3, 2]
    assert plain.reranker_model is None
    assert repo.saved[1].reranker_model is None


def test_trace_rejects_rerank_without_model_and_invalid_ranks() -> None:
    match = _match(1)
    kwargs = dict(
        knowledge_base_id=uuid4(),
        mode=RetrievalTraceMode.HYBRID,
        query="q",
        top_k=2,
        candidate_k=3,
        rrf_k=60,
        duration_ms=1.2,
        embedding_provider="openai",
        embedding_model="embedding-model",
        embedding_dimensions=1536,
    )
    from spurel.retrieval.traced import _hybrid_trace_results

    bad = replace(match, candidate_rank=1, rerank_rank=2, rerank_score=0.5)
    with pytest.raises(RetrievalTraceValidationError):
        RetrievalTrace.create(**kwargs, results=_hybrid_trace_results([bad]), reranker_model="m")
    with pytest.raises(RetrievalTraceValidationError):
        RetrievalTrace.create(**kwargs, results=_hybrid_trace_results([bad]))
