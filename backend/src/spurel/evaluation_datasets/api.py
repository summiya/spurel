"""FastAPI endpoints for reusable evaluation datasets."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from spurel.embeddings.domain import EmbeddingError
from spurel.evaluation_datasets.dependencies import (
    get_evaluation_dataset_service,
    get_hybrid_dataset_evaluation_service,
    get_keyword_dataset_evaluation_service,
    get_vector_dataset_evaluation_service,
)
from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationDatasetValidationError,
)
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationExecutionService,
    DatasetEvaluationLimitError,
    DatasetEvaluationQueryError,
    DatasetEvaluationResult,
)
from spurel.evaluation_datasets.ports import EvaluationDatasetPersistenceError
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
    DatasetEvaluationExecutionService,
    Depends(get_vector_dataset_evaluation_service),
]

KeywordDatasetEvaluationServiceDependency = Annotated[
    DatasetEvaluationExecutionService,
    Depends(get_keyword_dataset_evaluation_service),
]

HybridDatasetEvaluationServiceDependency = Annotated[
    DatasetEvaluationExecutionService,
    Depends(get_hybrid_dataset_evaluation_service),
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
    result: DatasetEvaluationResult,
) -> DatasetEvaluationResponse:
    return DatasetEvaluationResponse(
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
        cases=[
            DatasetEvaluationCaseResponse(
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
            for case in result.cases
        ],
    )
