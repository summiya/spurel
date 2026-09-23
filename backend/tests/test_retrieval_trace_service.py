import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from spurel.retrieval.trace_service import (
    RetrievalTraceNotFoundError,
    RetrievalTraceQueryError,
    RetrievalTraceService,
)
from spurel.retrieval.tracing import (
    RetrievalTrace,
    RetrievalTraceMode,
    RetrievalTraceSummary,
)


class FakeTraceRepository:
    def __init__(self) -> None:
        self.summaries: tuple[RetrievalTraceSummary, ...] = ()
        self.trace: RetrievalTrace | None = None
        self.last_list_call: dict[str, object] | None = None
        self.last_get_call: dict[str, object] | None = None

    async def add(self, trace: RetrievalTrace) -> None:
        self.trace = trace

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[RetrievalTraceSummary]:
        self.last_list_call = {
            "knowledge_base_id": knowledge_base_id,
            "limit": limit,
            "offset": offset,
        }
        return self.summaries[offset : offset + limit]

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        trace_id: UUID,
    ) -> RetrievalTrace | None:
        self.last_get_call = {
            "knowledge_base_id": knowledge_base_id,
            "trace_id": trace_id,
        }
        if (
            self.trace is not None
            and self.trace.id == trace_id
            and self.trace.knowledge_base_id == knowledge_base_id
        ):
            return self.trace
        return None


def test_trace_history_preserves_knowledge_base_scope_and_pagination() -> None:
    knowledge_base_id = uuid4()
    repository = FakeTraceRepository()
    repository.summaries = (
        RetrievalTraceSummary(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            mode=RetrievalTraceMode.KEYWORD,
            query="authentication",
            top_k=10,
            candidate_k=None,
            rrf_k=None,
            duration_ms=4.5,
            embedding_provider=None,
            embedding_model=None,
            embedding_dimensions=None,
            result_count=3,
            created_at=datetime.now(UTC),
        ),
    )
    service = RetrievalTraceService(repository)

    result = asyncio.run(
        service.list_by_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            limit=25,
            offset=0,
        )
    )

    assert tuple(result) == repository.summaries
    assert repository.last_list_call == {
        "knowledge_base_id": knowledge_base_id,
        "limit": 25,
        "offset": 0,
    }


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (101, 0),
        (True, 0),
        (50, -1),
        (50, True),
    ],
)
def test_trace_history_rejects_invalid_pagination(
    limit: int,
    offset: int,
) -> None:
    service = RetrievalTraceService(FakeTraceRepository())

    with pytest.raises(RetrievalTraceQueryError):
        asyncio.run(
            service.list_by_knowledge_base(
                knowledge_base_id=uuid4(),
                limit=limit,
                offset=offset,
            )
        )


def test_trace_detail_returns_scoped_trace() -> None:
    knowledge_base_id = uuid4()
    trace_id = uuid4()
    repository = FakeTraceRepository()
    repository.trace = RetrievalTrace(
        id=trace_id,
        knowledge_base_id=knowledge_base_id,
        mode=RetrievalTraceMode.KEYWORD,
        query="query",
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        duration_ms=3.0,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        results=(),
        created_at=datetime.now(UTC),
    )
    service = RetrievalTraceService(repository)

    trace = asyncio.run(
        service.get_by_id(
            knowledge_base_id=knowledge_base_id,
            trace_id=trace_id,
        )
    )

    assert trace.id == trace_id
    assert repository.last_get_call == {
        "knowledge_base_id": knowledge_base_id,
        "trace_id": trace_id,
    }


def test_trace_detail_hides_trace_from_another_knowledge_base() -> None:
    repository = FakeTraceRepository()
    repository.trace = RetrievalTrace(
        id=uuid4(),
        knowledge_base_id=uuid4(),
        mode=RetrievalTraceMode.KEYWORD,
        query="query",
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        duration_ms=3.0,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        results=(),
        created_at=datetime.now(UTC),
    )
    service = RetrievalTraceService(repository)

    with pytest.raises(RetrievalTraceNotFoundError):
        asyncio.run(
            service.get_by_id(
                knowledge_base_id=uuid4(),
                trace_id=repository.trace.id,
            )
        )
