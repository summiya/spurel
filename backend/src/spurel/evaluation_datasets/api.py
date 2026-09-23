"""FastAPI endpoints for reusable evaluation datasets."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from spurel.evaluation_datasets.dependencies import get_evaluation_dataset_service
from spurel.evaluation_datasets.domain import EvaluationDatasetValidationError
from spurel.evaluation_datasets.ports import EvaluationDatasetPersistenceError
from spurel.evaluation_datasets.schemas import (
    CreateEvaluationCaseRequest,
    CreateEvaluationDatasetRequest,
    EvaluationCaseListResponse,
    EvaluationCaseResponse,
    EvaluationCaseSummaryResponse,
    EvaluationDatasetListResponse,
    EvaluationDatasetResponse,
    EvaluationJudgmentResponse,
)
from spurel.evaluation_datasets.service import (
    EvaluationDatasetNotFoundError,
    EvaluationDatasetService,
)
from spurel.retrieval.evaluation import RelevanceJudgment

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/evaluation-datasets",
    tags=["evaluation-datasets"],
)

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


def _case_response(case) -> EvaluationCaseResponse:
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
