import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.retrieval.keyword_domain import (
    KeywordRetrievalMatch,
    KeywordRetrievalQueryError,
)
from spurel.retrieval.keyword_service import KeywordRetrievalService


class FakeKeywordRetrievalRepository:
    def __init__(self) -> None:
        self.results: tuple[KeywordRetrievalMatch, ...] = ()
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
        return self.results


def test_keyword_search_normalizes_query_and_preserves_scope() -> None:
    knowledge_base_id = uuid4()
    repository = FakeKeywordRetrievalRepository()
    repository.results = (
        KeywordRetrievalMatch(
            chunk_id=uuid4(),
            document_id=uuid4(),
            chunk_index=2,
            text="authentication flow",
            start_offset=20,
            end_offset=39,
            keyword_score=0.72,
        ),
    )
    service = KeywordRetrievalService(repository)

    result = asyncio.run(
        service.search(
            knowledge_base_id=knowledge_base_id,
            query="  authentication flow  ",
            limit=5,
        )
    )

    assert tuple(result) == repository.results
    assert repository.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "query": "authentication flow",
        "limit": 5,
    }


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
def test_keyword_search_rejects_invalid_query_or_limit(
    query: str,
    limit: int,
) -> None:
    service = KeywordRetrievalService(FakeKeywordRetrievalRepository())

    with pytest.raises(KeywordRetrievalQueryError):
        asyncio.run(
            service.search(
                knowledge_base_id=uuid4(),
                query=query,
                limit=limit,
            )
        )
