import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from spurel.evaluation_datasets.domain import EvaluationCase
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationExecutionService,
    DatasetEvaluationLimitError,
    DatasetEvaluationMode,
    DatasetEvaluationQueryError,
    KeywordDatasetRetriever,
)
from spurel.evaluation_datasets.ports import EvaluationDatasetLoadLimitError
from spurel.evaluation_datasets.service import EvaluationDatasetNotFoundError
from spurel.retrieval.evaluation import RelevanceJudgment
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch


class FakeDatasetRepository:
    def __init__(self, cases: Sequence[EvaluationCase] | None) -> None:
        self.cases = cases
        self.fail_limit = False
        self.last_call: dict[str, object] | None = None

    async def load_cases_for_evaluation(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        max_cases: int,
        max_total_judgments: int,
    ) -> Sequence[EvaluationCase] | None:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "dataset_id": dataset_id,
            "max_cases": max_cases,
            "max_total_judgments": max_total_judgments,
        }
        if self.fail_limit:
            raise EvaluationDatasetLoadLimitError("too large")
        return self.cases


class FakeKeywordRetriever:
    def __init__(
        self,
        results_by_query: dict[str, tuple[UUID, ...]],
    ) -> None:
        self.results_by_query = results_by_query
        self.calls: list[tuple[UUID, str, int]] = []

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        self.calls.append((knowledge_base_id, query, limit))
        return tuple(
            KeywordRetrievalMatch(
                chunk_id=chunk_id,
                document_id=uuid4(),
                chunk_index=index,
                text=f"chunk-{index}",
                start_offset=index * 10,
                end_offset=(index * 10) + 7,
                keyword_score=1.0 - (index * 0.1),
            )
            for index, chunk_id in enumerate(
                self.results_by_query.get(query, ())[:limit]
            )
        )


def _case(
    *,
    dataset_id: UUID,
    query: str,
    judgments: tuple[RelevanceJudgment, ...],
) -> EvaluationCase:
    return EvaluationCase(
        id=uuid4(),
        dataset_id=dataset_id,
        query=query,
        judgments=judgments,
        created_at=datetime.now(UTC),
    )


def test_dataset_execution_computes_per_case_and_aggregate_metrics() -> None:
    knowledge_base_id = uuid4()
    dataset_id = uuid4()

    first_relevant = uuid4()
    first_missing_relevant = uuid4()
    second_non_relevant = uuid4()
    second_relevant = uuid4()

    first_case = _case(
        dataset_id=dataset_id,
        query="first query",
        judgments=(
            RelevanceJudgment(chunk_id=first_relevant, relevance=3),
            RelevanceJudgment(chunk_id=first_missing_relevant, relevance=1),
        ),
    )
    second_case = _case(
        dataset_id=dataset_id,
        query="second query",
        judgments=(
            RelevanceJudgment(chunk_id=second_non_relevant, relevance=0),
            RelevanceJudgment(chunk_id=second_relevant, relevance=2),
        ),
    )

    repository = FakeDatasetRepository((first_case, second_case))
    keyword = FakeKeywordRetriever(
        {
            "first query": (first_relevant,),
            "second query": (second_non_relevant, second_relevant),
        }
    )
    service = DatasetEvaluationExecutionService(
        repository=repository,
        retriever=KeywordDatasetRetriever(keyword),
        mode=DatasetEvaluationMode.KEYWORD,
    )

    result = asyncio.run(
        service.run(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            top_k=2,
        )
    )

    assert result.mode is DatasetEvaluationMode.KEYWORD
    assert result.case_count == 2
    assert result.embedding_provider is None
    assert result.cases[0].metrics.precision_at_k == pytest.approx(0.5)
    assert result.cases[0].metrics.recall_at_k == pytest.approx(0.5)
    assert result.cases[0].metrics.reciprocal_rank_at_k == pytest.approx(1.0)
    assert result.cases[1].metrics.precision_at_k == pytest.approx(0.5)
    assert result.cases[1].metrics.recall_at_k == pytest.approx(1.0)
    assert result.cases[1].metrics.reciprocal_rank_at_k == pytest.approx(0.5)
    assert result.mean_precision_at_k == pytest.approx(0.5)
    assert result.mean_recall_at_k == pytest.approx(0.75)
    assert result.mrr_at_k == pytest.approx(0.75)
    assert result.mean_ndcg_at_k >= 0
    assert result.total_duration_ms >= 0
    assert result.mean_duration_ms >= 0
    assert keyword.calls == [
        (knowledge_base_id, "first query", 2),
        (knowledge_base_id, "second query", 2),
    ]


def test_dataset_execution_returns_not_found_for_unscoped_dataset() -> None:
    service = DatasetEvaluationExecutionService(
        repository=FakeDatasetRepository(None),
        retriever=KeywordDatasetRetriever(FakeKeywordRetriever({})),
        mode=DatasetEvaluationMode.KEYWORD,
    )

    with pytest.raises(EvaluationDatasetNotFoundError):
        asyncio.run(
            service.run(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                top_k=10,
            )
        )


def test_dataset_execution_rejects_empty_dataset() -> None:
    service = DatasetEvaluationExecutionService(
        repository=FakeDatasetRepository(()),
        retriever=KeywordDatasetRetriever(FakeKeywordRetriever({})),
        mode=DatasetEvaluationMode.KEYWORD,
    )

    with pytest.raises(DatasetEvaluationQueryError):
        asyncio.run(
            service.run(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                top_k=10,
            )
        )


def test_dataset_execution_translates_repository_load_limit() -> None:
    repository = FakeDatasetRepository(())
    repository.fail_limit = True
    service = DatasetEvaluationExecutionService(
        repository=repository,
        retriever=KeywordDatasetRetriever(FakeKeywordRetriever({})),
        mode=DatasetEvaluationMode.KEYWORD,
    )

    with pytest.raises(DatasetEvaluationLimitError):
        asyncio.run(
            service.run(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                top_k=10,
            )
        )


def test_keyword_dataset_execution_rejects_hybrid_configuration() -> None:
    service = DatasetEvaluationExecutionService(
        repository=FakeDatasetRepository(()),
        retriever=KeywordDatasetRetriever(FakeKeywordRetriever({})),
        mode=DatasetEvaluationMode.KEYWORD,
    )

    with pytest.raises(DatasetEvaluationQueryError):
        asyncio.run(
            service.run(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                top_k=10,
                candidate_k=50,
                rrf_k=60,
            )
        )


def test_vector_mode_requires_complete_embedding_configuration() -> None:
    service = DatasetEvaluationExecutionService(
        repository=FakeDatasetRepository(()),
        retriever=KeywordDatasetRetriever(FakeKeywordRetriever({})),
        mode=DatasetEvaluationMode.VECTOR,
    )

    with pytest.raises(DatasetEvaluationQueryError):
        asyncio.run(
            service.run(
                knowledge_base_id=uuid4(),
                dataset_id=uuid4(),
                top_k=10,
            )
        )
