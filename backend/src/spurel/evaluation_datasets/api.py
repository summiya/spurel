"""FastAPI endpoints for reusable evaluation datasets."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from spurel.embeddings.domain import EmbeddingError
from spurel.evaluation_datasets.dependencies import (
    get_evaluation_dataset_service,
    get_evaluation_run_comparison_service,
    get_evaluation_run_service,
    get_hybrid_dataset_evaluation_service,
    get_keyword_dataset_evaluation_service,
    get_vector_dataset_evaluation_service,
)
from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationDatasetValidationError,
)
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationLimitError,
    DatasetEvaluationQueryError,
)
from spurel.evaluation_datasets.ports import EvaluationDatasetPersistenceError
from spurel.evaluation_datasets.run_comparison import (
    EvaluationRunComparison,
    EvaluationRunComparisonQueryError,
    EvaluationRunComparisonService,
    EvaluationRunComparisonSide,
)
from spurel.evaluation_datasets.run_domain import EvaluationRun, EvaluationRunSummary
from spurel.evaluation_datasets.run_ports import EvaluationRunPersistenceError
from spurel.evaluation_datasets.run_service import (
    EvaluationRunNotFoundError,
    EvaluationRunService,
    PersistedDatasetEvaluationService,
)
from spurel.evaluation_datasets.schemas import (
    CreateEvaluationCaseRequest,
    CreateEvaluationDatasetRequest,
    DatasetEvaluationCaseResponse,
    DatasetEvaluationRequest,
    DatasetEvaluationResponse,
    EvaluationCaseListResponse,
    EvaluationCaseResponse,
    EvaluationCaseSummaryResponse,
    EvaluationDatasetListResponse,
    EvaluationDatasetResponse,
    EvaluationJudgmentResponse,
    EvaluationRunCaseComparisonResponse,
    EvaluationRunComparisonRequest,
    EvaluationRunComparisonResponse,
    EvaluationRunComparisonSideResponse,
    EvaluationRunListResponse,
    EvaluationRunSummaryResponse,
    HybridDatasetEvaluationRequest,
)
from spurel.evaluation_datasets.service import (
    EvaluationDatasetNotFoundError,
    EvaluationDatasetService,
)
from spurel.retrieval.domain import VectorRetrievalQueryError
from spurel.retrieval.evaluation import (
    RelevanceJudgment,
    RetrievalEvaluationQueryError,
)
from spurel.retrieval.hybrid import (
    HybridRetrievalQueryError,
    HybridRetrievalResultError,
)
from spurel.retrieval.keyword_domain import KeywordRetrievalQueryError
from spurel.retrieval.keyword_ports import KeywordRetrievalRepositoryError
from spurel.retrieval.ports import VectorRetrievalRepositoryError
from spurel.retrieval.service import VectorRetrievalProviderContractError

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/evaluation-datasets",
    tags=["evaluation-datasets"],
)

VectorDatasetEvaluationServiceDependency = Annotated[
    PersistedDatasetEvaluationService,
    Depends(get_vector_dataset_evaluation_service),
]

KeywordDatasetEvaluationServiceDependency = Annotated[
    PersistedDatasetEvaluationService,
    Depends(get_keyword_dataset_evaluation_service),
]

HybridDatasetEvaluationServiceDependency = Annotated[
    PersistedDatasetEvaluationService,
    Depends(get_hybrid_dataset_evaluation_service),
]

EvaluationRunComparisonServiceDependency = Annotated[
    EvaluationRunComparisonService,
    Depends(get_evaluation_run_comparison_service),
]

EvaluationRunServiceDependency = Annotated[
    EvaluationRunService,
    Depends(get_evaluation_run_service),
]

EvaluationDatasetServiceDependency = Annotated[
    EvaluationDatasetService,
    Depends(get_evaluation_dataset_service),
]


@router.post(
    "",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_dataset(
    knowledge_base_id: UUID,
    payload: CreateEvaluationDatasetRequest,
    service: EvaluationDatasetServiceDependency,
) -> EvaluationDatasetResponse:
    """Create one reusable evaluation dataset."""
    try:
        dataset = await service.create_dataset(
            knowledge_base_id=knowledge_base_id,
            name=payload.name,
        )
    except EvaluationDatasetValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="evaluation dataset request is invalid",
        ) from exc
    except EvaluationDatasetPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation dataset service temporarily unavailable",
        ) from exc

    return EvaluationDatasetResponse(
        id=dataset.id,
        knowledge_base_id=dataset.knowledge_base_id,
        name=dataset.name,
        case_count=0,
        created_at=dataset.created_at,
    )


@router.get("", response_model=EvaluationDatasetListResponse)
async def list_evaluation_datasets(
    knowledge_base_id: UUID,
    service: EvaluationDatasetServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvaluationDatasetListResponse:
    """List a bounded newest-first dataset page."""
    try:
        datasets = await service.list_datasets(
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            offset=offset,
        )
    except EvaluationDatasetPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation dataset service temporarily unavailable",
        ) from exc

    return EvaluationDatasetListResponse(
        items=[
            EvaluationDatasetResponse(
                id=item.dataset.id,
                knowledge_base_id=item.dataset.knowledge_base_id,
                name=item.dataset.name,
                case_count=item.case_count,
                created_at=item.dataset.created_at,
            )
            for item in datasets
        ],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{dataset_id}/cases",
    response_model=EvaluationCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_case(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    payload: CreateEvaluationCaseRequest,
    service: EvaluationDatasetServiceDependency,
) -> EvaluationCaseResponse:
    """Create one labeled query and persist all judgments atomically."""
    try:
        case = await service.add_case(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            query=payload.query,
            judgments=tuple(
                RelevanceJudgment(
                    chunk_id=judgment.chunk_id,
                    relevance=judgment.relevance,
                )
                for judgment in payload.judgments
            ),
        )
    except EvaluationDatasetValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="evaluation case request is invalid",
        ) from exc
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation dataset was not found",
        ) from exc
    except EvaluationDatasetPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation dataset service temporarily unavailable",
        ) from exc

    return _case_response(case)


@router.get(
    "/{dataset_id}/cases",
    response_model=EvaluationCaseListResponse,
)
async def list_evaluation_cases(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    service: EvaluationDatasetServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvaluationCaseListResponse:
    """List lightweight cases without loading all judgments."""
    try:
        cases = await service.list_cases(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            limit=limit,
            offset=offset,
        )
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation dataset was not found",
        ) from exc
    except EvaluationDatasetPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation dataset service temporarily unavailable",
        ) from exc

    return EvaluationCaseListResponse(
        items=[
            EvaluationCaseSummaryResponse(
                id=item.id,
                dataset_id=item.dataset_id,
                query=item.query,
                judgment_count=item.judgment_count,
                relevant_judgment_count=item.relevant_judgment_count,
                created_at=item.created_at,
            )
            for item in cases
        ],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{dataset_id}/cases/{case_id}",
    response_model=EvaluationCaseResponse,
)
async def get_evaluation_case(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    case_id: UUID,
    service: EvaluationDatasetServiceDependency,
) -> EvaluationCaseResponse:
    """Return one scoped evaluation case with all relevance judgments."""
    try:
        case = await service.get_case(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            case_id=case_id,
        )
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation case was not found",
        ) from exc
    except EvaluationDatasetPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation dataset service temporarily unavailable",
        ) from exc

    return _case_response(case)


def _case_response(case: EvaluationCase) -> EvaluationCaseResponse:
    return EvaluationCaseResponse(
        id=case.id,
        dataset_id=case.dataset_id,
        query=case.query,
        judgments=[
            EvaluationJudgmentResponse(
                chunk_id=judgment.chunk_id,
                relevance=judgment.relevance,
            )
            for judgment in case.judgments
        ],
        created_at=case.created_at,
    )


@router.post(
    "/{dataset_id}/evaluate/vector",
    response_model=DatasetEvaluationResponse,
)
async def evaluate_dataset_vector(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    payload: DatasetEvaluationRequest,
    service: VectorDatasetEvaluationServiceDependency,
) -> DatasetEvaluationResponse:
    """Evaluate every labeled query with vector retrieval."""
    try:
        result = await service.run(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            top_k=payload.top_k,
        )
    except DatasetEvaluationQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset evaluation request is invalid",
        ) from exc
    except DatasetEvaluationLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset exceeds synchronous evaluation limits",
        ) from exc
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation dataset was not found",
        ) from exc
    except (
        EvaluationDatasetPersistenceError,
        EvaluationRunPersistenceError,
        EmbeddingError,
        VectorRetrievalProviderContractError,
        VectorRetrievalQueryError,
        VectorRetrievalRepositoryError,
        RetrievalEvaluationQueryError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dataset evaluation temporarily unavailable",
        ) from exc

    return _dataset_evaluation_response(result)


@router.post(
    "/{dataset_id}/evaluate/keyword",
    response_model=DatasetEvaluationResponse,
)
async def evaluate_dataset_keyword(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    payload: DatasetEvaluationRequest,
    service: KeywordDatasetEvaluationServiceDependency,
) -> DatasetEvaluationResponse:
    """Evaluate every labeled query with keyword retrieval."""
    try:
        result = await service.run(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            top_k=payload.top_k,
        )
    except DatasetEvaluationQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset evaluation request is invalid",
        ) from exc
    except DatasetEvaluationLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset exceeds synchronous evaluation limits",
        ) from exc
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation dataset was not found",
        ) from exc
    except (
        EvaluationDatasetPersistenceError,
        EvaluationRunPersistenceError,
        KeywordRetrievalQueryError,
        KeywordRetrievalRepositoryError,
        RetrievalEvaluationQueryError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dataset evaluation temporarily unavailable",
        ) from exc

    return _dataset_evaluation_response(result)


@router.post(
    "/{dataset_id}/evaluate/hybrid",
    response_model=DatasetEvaluationResponse,
)
async def evaluate_dataset_hybrid(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    payload: HybridDatasetEvaluationRequest,
    service: HybridDatasetEvaluationServiceDependency,
) -> DatasetEvaluationResponse:
    """Evaluate every labeled query with vector + keyword hybrid retrieval."""
    try:
        result = await service.run(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            top_k=payload.top_k,
            candidate_k=payload.candidate_k,
            rrf_k=payload.rrf_k,
        )
    except DatasetEvaluationQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset evaluation request is invalid",
        ) from exc
    except DatasetEvaluationLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dataset exceeds synchronous evaluation limits",
        ) from exc
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation dataset was not found",
        ) from exc
    except (
        EvaluationDatasetPersistenceError,
        EvaluationRunPersistenceError,
        EmbeddingError,
        VectorRetrievalProviderContractError,
        VectorRetrievalRepositoryError,
        KeywordRetrievalRepositoryError,
        HybridRetrievalQueryError,
        HybridRetrievalResultError,
        RetrievalEvaluationQueryError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dataset evaluation temporarily unavailable",
        ) from exc

    return _dataset_evaluation_response(result)


def _dataset_evaluation_response(
    run: EvaluationRun,
) -> DatasetEvaluationResponse:
    return DatasetEvaluationResponse(
        run_id=run.id,
        knowledge_base_id=run.knowledge_base_id,
        dataset_id=run.dataset_id,
        mode=run.mode,
        top_k=run.top_k,
        candidate_k=run.candidate_k,
        rrf_k=run.rrf_k,
        embedding_provider=run.embedding_provider,
        embedding_model=run.embedding_model,
        embedding_dimensions=run.embedding_dimensions,
        case_count=run.case_count,
        total_duration_ms=run.total_duration_ms,
        mean_duration_ms=run.mean_duration_ms,
        judgment_coverage_case_count=run.judgment_coverage_case_count,
        mean_judgment_coverage_at_k=run.mean_judgment_coverage_at_k,
        mean_precision_at_k=run.mean_precision_at_k,
        mean_recall_at_k=run.mean_recall_at_k,
        mrr_at_k=run.mrr_at_k,
        mean_ndcg_at_k=run.mean_ndcg_at_k,
        created_at=run.created_at,
        cases=[
            DatasetEvaluationCaseResponse(
                position=case.position,
                case_id=case.case_id,
                query=case.query,
                duration_ms=case.duration_ms,
                judged_count=case.metrics.judged_count,
                relevant_count=case.metrics.relevant_count,
                retrieved_count_at_k=case.metrics.retrieved_count_at_k,
                judged_retrieved_at_k=case.metrics.judged_retrieved_at_k,
                relevant_retrieved_at_k=case.metrics.relevant_retrieved_at_k,
                judgment_coverage_at_k=case.metrics.judgment_coverage_at_k,
                precision_at_k=case.metrics.precision_at_k,
                recall_at_k=case.metrics.recall_at_k,
                reciprocal_rank_at_k=case.metrics.reciprocal_rank_at_k,
                ndcg_at_k=case.metrics.ndcg_at_k,
            )
            for case in run.cases
        ],
    )


@router.get(
    "/{dataset_id}/runs",
    response_model=EvaluationRunListResponse,
)
async def list_evaluation_runs(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    service: EvaluationRunServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvaluationRunListResponse:
    """Return bounded newest-first benchmark history for one dataset identity."""
    try:
        runs = await service.list_by_dataset(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            limit=limit,
            offset=offset,
        )
    except EvaluationRunPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation run history temporarily unavailable",
        ) from exc

    return EvaluationRunListResponse(
        items=[_run_summary_response(run) for run in runs],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{dataset_id}/runs/{run_id}",
    response_model=DatasetEvaluationResponse,
)
async def get_evaluation_run(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    run_id: UUID,
    service: EvaluationRunServiceDependency,
) -> DatasetEvaluationResponse:
    """Return one scoped persisted benchmark with all per-case metrics."""
    try:
        run = await service.get_by_id(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            run_id=run_id,
        )
    except EvaluationRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation run was not found",
        ) from exc
    except EvaluationRunPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation run history temporarily unavailable",
        ) from exc

    return _dataset_evaluation_response(run)


def _run_summary_response(
    run: EvaluationRunSummary,
) -> EvaluationRunSummaryResponse:
    return EvaluationRunSummaryResponse(
        run_id=run.id,
        dataset_id=run.dataset_id,
        mode=run.mode,
        top_k=run.top_k,
        candidate_k=run.candidate_k,
        rrf_k=run.rrf_k,
        embedding_provider=run.embedding_provider,
        embedding_model=run.embedding_model,
        embedding_dimensions=run.embedding_dimensions,
        case_count=run.case_count,
        total_duration_ms=run.total_duration_ms,
        mean_duration_ms=run.mean_duration_ms,
        judgment_coverage_case_count=run.judgment_coverage_case_count,
        mean_judgment_coverage_at_k=run.mean_judgment_coverage_at_k,
        mean_precision_at_k=run.mean_precision_at_k,
        mean_recall_at_k=run.mean_recall_at_k,
        mrr_at_k=run.mrr_at_k,
        mean_ndcg_at_k=run.mean_ndcg_at_k,
        created_at=run.created_at,
    )


@router.post(
    "/{dataset_id}/run-comparisons",
    response_model=EvaluationRunComparisonResponse,
)
async def compare_evaluation_runs(
    knowledge_base_id: UUID,
    dataset_id: UUID,
    payload: EvaluationRunComparisonRequest,
    service: EvaluationRunComparisonServiceDependency,
) -> EvaluationRunComparisonResponse:
    """Compare two scoped persisted benchmark runs."""
    try:
        comparison = await service.compare(
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset_id,
            first_run_id=payload.first_run_id,
            second_run_id=payload.second_run_id,
        )
    except EvaluationRunComparisonQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="evaluation run comparison request is invalid",
        ) from exc
    except EvaluationRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="evaluation run was not found",
        ) from exc
    except EvaluationRunPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evaluation run comparison temporarily unavailable",
        ) from exc

    return _run_comparison_response(comparison)


def _run_comparison_response(
    comparison: EvaluationRunComparison,
) -> EvaluationRunComparisonResponse:
    return EvaluationRunComparisonResponse(
        dataset_id=comparison.dataset_id,
        first=_run_comparison_side_response(comparison.first),
        second=_run_comparison_side_response(comparison.second),
        same_retrieval_configuration=comparison.same_retrieval_configuration,
        same_case_set=comparison.same_case_set,
        aggregate_comparable=comparison.aggregate_comparable,
        shared_case_count=comparison.shared_case_count,
        first_only_case_count=comparison.first_only_case_count,
        second_only_case_count=comparison.second_only_case_count,
        comparable_case_count=comparison.comparable_case_count,
        query_changed_case_count=comparison.query_changed_case_count,
        total_duration_delta_ms=comparison.total_duration_delta_ms,
        mean_duration_delta_ms=comparison.mean_duration_delta_ms,
        mean_judgment_coverage_delta=comparison.mean_judgment_coverage_delta,
        mean_precision_delta=comparison.mean_precision_delta,
        mean_recall_delta=comparison.mean_recall_delta,
        mrr_delta=comparison.mrr_delta,
        mean_ndcg_delta=comparison.mean_ndcg_delta,
        cases=[
            EvaluationRunCaseComparisonResponse(
                case_id=case.case_id,
                presence=case.presence,
                first_position=case.first_position,
                second_position=case.second_position,
                first_query=case.first_query,
                second_query=case.second_query,
                query_changed=case.query_changed,
                comparable=case.comparable,
                first_duration_ms=case.first_duration_ms,
                second_duration_ms=case.second_duration_ms,
                duration_delta_ms=case.duration_delta_ms,
                first_precision_at_k=case.first_precision_at_k,
                second_precision_at_k=case.second_precision_at_k,
                precision_delta=case.precision_delta,
                first_recall_at_k=case.first_recall_at_k,
                second_recall_at_k=case.second_recall_at_k,
                recall_delta=case.recall_delta,
                first_reciprocal_rank_at_k=case.first_reciprocal_rank_at_k,
                second_reciprocal_rank_at_k=case.second_reciprocal_rank_at_k,
                reciprocal_rank_delta=case.reciprocal_rank_delta,
                first_ndcg_at_k=case.first_ndcg_at_k,
                second_ndcg_at_k=case.second_ndcg_at_k,
                ndcg_delta=case.ndcg_delta,
            )
            for case in comparison.cases
        ],
    )


def _run_comparison_side_response(
    side: EvaluationRunComparisonSide,
) -> EvaluationRunComparisonSideResponse:
    return EvaluationRunComparisonSideResponse(
        run_id=side.run_id,
        mode=side.mode,
        top_k=side.top_k,
        candidate_k=side.candidate_k,
        rrf_k=side.rrf_k,
        embedding_provider=side.embedding_provider,
        embedding_model=side.embedding_model,
        embedding_dimensions=side.embedding_dimensions,
        case_count=side.case_count,
        total_duration_ms=side.total_duration_ms,
        mean_duration_ms=side.mean_duration_ms,
        judgment_coverage_case_count=side.judgment_coverage_case_count,
        mean_judgment_coverage_at_k=side.mean_judgment_coverage_at_k,
        mean_precision_at_k=side.mean_precision_at_k,
        mean_recall_at_k=side.mean_recall_at_k,
        mrr_at_k=side.mrr_at_k,
        mean_ndcg_at_k=side.mean_ndcg_at_k,
    )
