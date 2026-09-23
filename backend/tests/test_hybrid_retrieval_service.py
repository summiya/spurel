import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.hybrid import (
    HybridRetrievalQueryError,
    HybridRetrievalResultError,
    HybridRetrievalService,
)
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch


class FakeVectorRetriever:
    def __init__(self, results: Sequence[VectorRetrievalMatch]) -> None:
        self.results = tuple(results)
        self.last_call: dict[str, object] | None = None

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "query": query,
            "limit": limit,
        }
        return self.results[:limit]


class FakeKeywordRetriever:
    def __init__(self, results: Sequence[KeywordRetrievalMatch]) -> None:
        self.results = tuple(results)
        self.last_call: dict[str, object] | None = None

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "query": query,
            "limit": limit,
        }
        return self.results[:limit]


def _vector_match(
    *,
    chunk_id: UUID,
    document_id: UUID,
    index: int,
    score: float,
) -> VectorRetrievalMatch:
    return VectorRetrievalMatch(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=index,
        text=f"chunk-{index}",
        start_offset=index * 10,
        end_offset=(index * 10) + 7,
        cosine_similarity=score,
    )


def _keyword_match(
    *,
    chunk_id: UUID,
    document_id: UUID,
    index: int,
    score: float,
) -> KeywordRetrievalMatch:
    return KeywordRetrievalMatch(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=index,
        text=f"chunk-{index}",
        start_offset=index * 10,
        end_offset=(index * 10) + 7,
        keyword_score=score,
    )


def test_hybrid_search_fuses_duplicate_chunks_and_preserves_source_scores() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    shared = uuid4()
    vector_only = uuid4()
    keyword_only = uuid4()

    vector = FakeVectorRetriever(
        (
            _vector_match(
                chunk_id=shared,
                document_id=document_id,
                index=0,
                score=0.91,
            ),
            _vector_match(
                chunk_id=vector_only,
                document_id=document_id,
                index=1,
                score=0.87,
            ),
        )
    )
    keyword = FakeKeywordRetriever(
        (
            _keyword_match(
                chunk_id=keyword_only,
                document_id=document_id,
                index=2,
                score=0.8,
            ),
            _keyword_match(
                chunk_id=shared,
                document_id=document_id,
                index=0,
                score=0.7,
            ),
        )
    )

    service = HybridRetrievalService(
        vector_retriever=vector,
        keyword_retriever=keyword,
    )

    result = asyncio.run(
        service.search(
            knowledge_base_id=knowledge_base_id,
            query="  authentication  ",
            limit=3,
            candidate_limit=10,
            rrf_k=60,
        )
    )

    assert result[0].chunk_id == shared
    assert result[0].vector_rank == 1
    assert result[0].keyword_rank == 2
    assert result[0].cosine_similarity == 0.91
    assert result[0].keyword_score == 0.7
    assert result[0].rrf_score == pytest.approx((1 / 61) + (1 / 62))
    assert vector.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "query": "authentication",
        "limit": 10,
    }
    assert keyword.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "query": "authentication",
        "limit": 10,
    }


def test_hybrid_search_uses_deterministic_rrf_order() -> None:
    document_id = uuid4()
    first = uuid4()
    second = uuid4()

    service = HybridRetrievalService(
        vector_retriever=FakeVectorRetriever(
            (
                _vector_match(
                    chunk_id=first,
                    document_id=document_id,
                    index=0,
                    score=0.99,
                ),
                _vector_match(
                    chunk_id=second,
                    document_id=document_id,
                    index=1,
                    score=0.98,
                ),
            )
        ),
        keyword_retriever=FakeKeywordRetriever(
            (
                _keyword_match(
                    chunk_id=second,
                    document_id=document_id,
                    index=1,
                    score=0.9,
                ),
                _keyword_match(
                    chunk_id=first,
                    document_id=document_id,
                    index=0,
                    score=0.8,
                ),
            )
        ),
    )

    result = asyncio.run(
        service.search(
            knowledge_base_id=uuid4(),
            query="query",
            limit=2,
            candidate_limit=2,
            rrf_k=60,
        )
    )

    assert {match.chunk_id for match in result} == {first, second}
    assert result[0].rrf_score == pytest.approx(result[1].rrf_score)


@pytest.mark.parametrize(
    ("query", "limit", "candidate_limit", "rrf_k"),
    [
        ("", 10, 50, 60),
        ("query", 0, 50, 60),
        ("query", 10, 9, 60),
        ("query", 10, 101, 60),
        ("query", 10, 50, 0),
        ("query", True, 50, 60),
    ],
)
def test_hybrid_search_rejects_invalid_parameters(
    query: str,
    limit: int,
    candidate_limit: int,
    rrf_k: int,
) -> None:
    service = HybridRetrievalService(
        vector_retriever=FakeVectorRetriever(()),
        keyword_retriever=FakeKeywordRetriever(()),
    )

    with pytest.raises(HybridRetrievalQueryError):
        asyncio.run(
            service.search(
                knowledge_base_id=uuid4(),
                query=query,
                limit=limit,
                candidate_limit=candidate_limit,
                rrf_k=rrf_k,
            )
        )


def test_hybrid_search_rejects_inconsistent_shared_chunk_metadata() -> None:
    document_id = uuid4()
    chunk_id = uuid4()
    vector = _vector_match(
        chunk_id=chunk_id,
        document_id=document_id,
        index=0,
        score=0.9,
    )
    keyword = KeywordRetrievalMatch(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        text="different persisted text",
        start_offset=0,
        end_offset=7,
        keyword_score=0.8,
    )
    service = HybridRetrievalService(
        vector_retriever=FakeVectorRetriever((vector,)),
        keyword_retriever=FakeKeywordRetriever((keyword,)),
    )

    with pytest.raises(HybridRetrievalResultError):
        asyncio.run(
            service.search(
                knowledge_base_id=uuid4(),
                query="query",
            )
        )
