"""Execute reusable evaluation datasets against retrieval configurations."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter
from typing import Protocol
from uuid import UUID

from spurel.evaluation_datasets.domain import EvaluationCase
from spurel.evaluation_datasets.ports import (
    EvaluationDatasetLoadLimitError,
    EvaluationDatasetRepository,
)
from spurel.evaluation_datasets.service import EvaluationDatasetNotFoundError
from spurel.retrieval.domain import VectorRetrievalMatch
from spurel.retrieval.evaluation import (
    RetrievalMetricValues,
    calculate_retrieval_metrics,
)
from spurel.retrieval.hybrid import HybridRetrievalMatch
from spurel.retrieval.keyword_domain import KeywordRetrievalMatch

MAX_DATASET_EVALUATION_CASES = 100
MAX_DATASET_EVALUATION_JUDGMENTS = 50_000
MAX_DATASET_EVALUATION_TOP_K = 100


class DatasetEvaluationMode(StrEnum):
    """Supported retrieval modes for dataset evaluation."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class DatasetEvaluationQueryError(ValueError):
    """Raised when dataset evaluation configuration is invalid."""


class DatasetEvaluationLimitError(ValueError):
    """Raised when a dataset is too large for synchronous evaluation."""


class VectorSearchRunner(Protocol):
    """Vector search capability required by the vector adapter."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[VectorRetrievalMatch]:
        """Return ranked vector matches."""
        ...


class KeywordSearchRunner(Protocol):
    """Keyword search capability required by the keyword adapter."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
    ) -> Sequence[KeywordRetrievalMatch]:
        """Return ranked keyword matches."""
        ...


class HybridSearchRunner(Protocol):
    """Hybrid search capability required by the hybrid adapter."""

    async def search(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        limit: int,
        candidate_limit: int,
        rrf_k: int,
    ) -> Sequence[HybridRetrievalMatch]:
        """Return ranked hybrid matches."""
        ...


class DatasetRetriever(Protocol):
    """Mode-specific retrieval adapter used by dataset execution."""

    async def retrieve(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        top_k: int,
        candidate_k: int | None,
        rrf_k: int | None,
    ) -> Sequence[UUID]:
        """Return ranked chunk IDs for one evaluation query."""
        ...


@dataclass(frozen=True, slots=True)
class DatasetEvaluationCaseResult:
    """Metrics for one labeled query in a dataset run."""

    case_id: UUID
    query: str
    duration_ms: float
    metrics: RetrievalMetricValues


@dataclass(frozen=True, slots=True)
class DatasetEvaluationResult:
    """Aggregate metrics for one full reusable dataset run."""

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
    mean_judgment_coverage_at_k: float | None
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr_at_k: float
    mean_ndcg_at_k: float
    cases: tuple[DatasetEvaluationCaseResult, ...]


class VectorDatasetRetriever:
    """Adapt vector retrieval to ranked chunk IDs."""

    def __init__(self, retriever: VectorSearchRunner) -> None:
        self._retriever = retriever

    async def retrieve(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        top_k: int,
        candidate_k: int | None,
        rrf_k: int | None,
    ) -> Sequence[UUID]:
        del candidate_k, rrf_k
        matches = await self._retriever.search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            limit=top_k,
        )
        return tuple(match.chunk_id for match in matches)


class KeywordDatasetRetriever:
    """Adapt keyword retrieval to ranked chunk IDs."""

    def __init__(self, retriever: KeywordSearchRunner) -> None:
        self._retriever = retriever

    async def retrieve(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        top_k: int,
        candidate_k: int | None,
        rrf_k: int | None,
    ) -> Sequence[UUID]:
        del candidate_k, rrf_k
        matches = await self._retriever.search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            limit=top_k,
        )
        return tuple(match.chunk_id for match in matches)


class HybridDatasetRetriever:
    """Adapt hybrid retrieval to ranked chunk IDs."""

    def __init__(self, retriever: HybridSearchRunner) -> None:
        self._retriever = retriever

    async def retrieve(
        self,
        *,
        knowledge_base_id: UUID,
        query: str,
        top_k: int,
        candidate_k: int | None,
        rrf_k: int | None,
    ) -> Sequence[UUID]:
        assert candidate_k is not None
        assert rrf_k is not None
        matches = await self._retriever.search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            limit=top_k,
            candidate_limit=candidate_k,
            rrf_k=rrf_k,
        )
        return tuple(match.chunk_id for match in matches)


class DatasetEvaluationExecutionService:
    """Run a bounded evaluation dataset against one retrieval configuration."""

    def __init__(
        self,
        *,
        repository: EvaluationDatasetRepository,
        retriever: DatasetRetriever,
        mode: DatasetEvaluationMode,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
    ) -> None:
        self._repository = repository
        self._retriever = retriever
        self._mode = mode
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        dataset_id: UUID,
        top_k: int,
        candidate_k: int | None = None,
        rrf_k: int | None = None,
    ) -> DatasetEvaluationResult:
        """Execute every labeled query sequentially and aggregate its metrics."""
        _validate_configuration(
            mode=self._mode,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=rrf_k,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_dimensions=self._embedding_dimensions,
        )

        try:
            cases = await self._repository.load_cases_for_evaluation(
                knowledge_base_id=knowledge_base_id,
                dataset_id=dataset_id,
                max_cases=MAX_DATASET_EVALUATION_CASES,
                max_total_judgments=MAX_DATASET_EVALUATION_JUDGMENTS,
            )
        except EvaluationDatasetLoadLimitError as exc:
            raise DatasetEvaluationLimitError(
                "dataset exceeds synchronous evaluation limits"
            ) from exc

        if cases is None:
            raise EvaluationDatasetNotFoundError(
                "evaluation dataset was not found"
            )
        if not cases:
            raise DatasetEvaluationQueryError(
                "evaluation dataset must contain at least one case"
            )

        case_results: list[DatasetEvaluationCaseResult] = []
        for case in cases:
            case_results.append(
                await self._evaluate_case(
                    knowledge_base_id=knowledge_base_id,
                    case=case,
                    top_k=top_k,
                    candidate_k=candidate_k,
                    rrf_k=rrf_k,
                )
            )

        return _aggregate(
            dataset_id=dataset_id,
            mode=self._mode,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=rrf_k,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_dimensions=self._embedding_dimensions,
            cases=tuple(case_results),
        )

    async def _evaluate_case(
        self,
        *,
        knowledge_base_id: UUID,
        case: EvaluationCase,
        top_k: int,
        candidate_k: int | None,
        rrf_k: int | None,
    ) -> DatasetEvaluationCaseResult:
        started = perf_counter()
        ranked_chunk_ids = tuple(
            await self._retriever.retrieve(
                knowledge_base_id=knowledge_base_id,
                query=case.query,
                top_k=top_k,
                candidate_k=candidate_k,
                rrf_k=rrf_k,
            )
        )
        duration_ms = max(0.0, (perf_counter() - started) * 1_000.0)

        metrics = calculate_retrieval_metrics(
            cutoff=top_k,
            ranked_chunk_ids=ranked_chunk_ids,
            judgments=case.judgments,
        )

        return DatasetEvaluationCaseResult(
            case_id=case.id,
            query=case.query,
            duration_ms=duration_ms,
            metrics=metrics,
        )


def _validate_configuration(
    *,
    mode: DatasetEvaluationMode,
    top_k: int,
    candidate_k: int | None,
    rrf_k: int | None,
    embedding_provider: str | None,
    embedding_model: str | None,
    embedding_dimensions: int | None,
) -> None:
    if (
        isinstance(top_k, bool)
        or not isinstance(top_k, int)
        or top_k < 1
        or top_k > MAX_DATASET_EVALUATION_TOP_K
    ):
        raise DatasetEvaluationQueryError(
            "dataset evaluation top_k is outside the supported range"
        )

    if mode is DatasetEvaluationMode.HYBRID:
        if (
            isinstance(candidate_k, bool)
            or not isinstance(candidate_k, int)
            or candidate_k < top_k
            or candidate_k > MAX_DATASET_EVALUATION_TOP_K
        ):
            raise DatasetEvaluationQueryError(
                "hybrid dataset evaluation candidate_k is invalid"
            )
        if (
            isinstance(rrf_k, bool)
            or not isinstance(rrf_k, int)
            or rrf_k < 1
            or rrf_k > 1_000
        ):
            raise DatasetEvaluationQueryError(
                "hybrid dataset evaluation rrf_k is invalid"
            )
    elif candidate_k is not None or rrf_k is not None:
        raise DatasetEvaluationQueryError(
            "non-hybrid dataset evaluation cannot contain hybrid configuration"
        )

    embedding_values = (
        embedding_provider,
        embedding_model,
        embedding_dimensions,
    )
    has_complete_embedding_space = all(
        value is not None for value in embedding_values
    )

    if mode in {DatasetEvaluationMode.VECTOR, DatasetEvaluationMode.HYBRID}:
        if not has_complete_embedding_space:
            raise DatasetEvaluationQueryError(
                "vector-based dataset evaluation requires embedding configuration"
            )

        assert embedding_provider is not None
        assert embedding_model is not None
        assert embedding_dimensions is not None
        if (
            not embedding_provider.strip()
            or not embedding_model.strip()
            or isinstance(embedding_dimensions, bool)
            or not isinstance(embedding_dimensions, int)
            or embedding_dimensions < 1
        ):
            raise DatasetEvaluationQueryError(
                "dataset evaluation embedding configuration is invalid"
            )
    elif any(value is not None for value in embedding_values):
        raise DatasetEvaluationQueryError(
            "keyword dataset evaluation cannot contain embedding configuration"
        )


def _aggregate(
    *,
    dataset_id: UUID,
    mode: DatasetEvaluationMode,
    top_k: int,
    candidate_k: int | None,
    rrf_k: int | None,
    embedding_provider: str | None,
    embedding_model: str | None,
    embedding_dimensions: int | None,
    cases: tuple[DatasetEvaluationCaseResult, ...],
) -> DatasetEvaluationResult:
    case_count = len(cases)
    total_duration_ms = sum(case.duration_ms for case in cases)
    coverage_values = tuple(
        case.metrics.judgment_coverage_at_k
        for case in cases
        if case.metrics.judgment_coverage_at_k is not None
    )
    mean_rr = sum(
        case.metrics.reciprocal_rank_at_k for case in cases
    ) / case_count

    return DatasetEvaluationResult(
        dataset_id=dataset_id,
        mode=mode,
        top_k=top_k,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        case_count=case_count,
        total_duration_ms=total_duration_ms,
        mean_duration_ms=total_duration_ms / case_count,
        mean_judgment_coverage_at_k=(
            sum(coverage_values) / len(coverage_values)
            if coverage_values
            else None
        ),
        mean_precision_at_k=sum(
            case.metrics.precision_at_k for case in cases
        )
        / case_count,
        mean_recall_at_k=sum(
            case.metrics.recall_at_k for case in cases
        )
        / case_count,
        mrr_at_k=mean_rr,
        mean_ndcg_at_k=sum(
            case.metrics.ndcg_at_k for case in cases
        )
        / case_count,
        cases=cases,
    )
