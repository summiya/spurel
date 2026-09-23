"""Historical evaluation run domain models."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from spurel.evaluation_datasets.execution import (
    DatasetEvaluationCaseResult,
    DatasetEvaluationMode,
    DatasetEvaluationResult,
)
from spurel.retrieval.evaluation import RetrievalMetricValues


@dataclass(frozen=True, slots=True)
class EvaluationRunCase:
    """Immutable per-query metric snapshot within one benchmark run."""

    position: int
    case_id: UUID
    query: str
    duration_ms: float
    metrics: RetrievalMetricValues


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    """Immutable persisted snapshot of one completed dataset benchmark."""

    id: UUID
    knowledge_base_id: UUID
    dataset_id: UUID
    mode: DatasetEvaluationMode
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    case_count: int
    total_duration_ms: float
    mean_duration_ms: float
    judgment_coverage_case_count: int
    mean_judgment_coverage_at_k: float | None
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr_at_k: float
    mean_ndcg_at_k: float
    cases: tuple[EvaluationRunCase, ...]
    created_at: datetime

    @classmethod
    def from_execution(
        cls,
        *,
        knowledge_base_id: UUID,
        result: DatasetEvaluationResult,
    ) -> "EvaluationRun":
        """Snapshot one successful in-memory evaluation result."""
        return cls(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            dataset_id=result.dataset_id,
            mode=result.mode,
            top_k=result.top_k,
            candidate_k=result.candidate_k,
            rrf_k=result.rrf_k,
            embedding_provider=result.embedding_provider,
            embedding_model=result.embedding_model,
            embedding_dimensions=result.embedding_dimensions,
            case_count=result.case_count,
            total_duration_ms=result.total_duration_ms,
            mean_duration_ms=result.mean_duration_ms,
            judgment_coverage_case_count=result.judgment_coverage_case_count,
            mean_judgment_coverage_at_k=result.mean_judgment_coverage_at_k,
            mean_precision_at_k=result.mean_precision_at_k,
            mean_recall_at_k=result.mean_recall_at_k,
            mrr_at_k=result.mrr_at_k,
            mean_ndcg_at_k=result.mean_ndcg_at_k,
            cases=tuple(
                _snapshot_case(position=position, result=case)
                for position, case in enumerate(result.cases, start=1)
            ),
            created_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class EvaluationRunSummary:
    """Lightweight benchmark history item without per-case rows."""

    id: UUID
    knowledge_base_id: UUID
    dataset_id: UUID
    mode: DatasetEvaluationMode
    top_k: int
    candidate_k: int | None
    rrf_k: int | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    case_count: int
    total_duration_ms: float
    mean_duration_ms: float
    judgment_coverage_case_count: int
    mean_judgment_coverage_at_k: float | None
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr_at_k: float
    mean_ndcg_at_k: float
    created_at: datetime


def _snapshot_case(
    *,
    position: int,
    result: DatasetEvaluationCaseResult,
) -> EvaluationRunCase:
    return EvaluationRunCase(
        position=position,
        case_id=result.case_id,
        query=result.query,
        duration_ms=result.duration_ms,
        metrics=result.metrics,
    )
