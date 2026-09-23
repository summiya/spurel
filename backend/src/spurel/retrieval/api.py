"""FastAPI boundary for the Retrieval Playground."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from spurel.embeddings.domain import EmbeddingError
from spurel.retrieval.dependencies import (
    get_traced_hybrid_retrieval_service,
    get_traced_keyword_retrieval_service,
    get_traced_vector_retrieval_service,
)
from spurel.retrieval.domain import VectorRetrievalQueryError
from spurel.retrieval.hybrid import (
    HybridRetrievalQueryError,
    HybridRetrievalResultError,
)
from spurel.retrieval.keyword_domain import KeywordRetrievalQueryError
from spurel.retrieval.keyword_ports import KeywordRetrievalRepositoryError
from spurel.retrieval.ports import VectorRetrievalRepositoryError
from spurel.retrieval.schemas import (
    HybridRetrievalMatchResponse,
    HybridRetrievalRequest,
    HybridRetrievalResponse,
    KeywordRetrievalMatchResponse,
    KeywordRetrievalRequest,
    KeywordRetrievalResponse,
    VectorRetrievalMatchResponse,
    VectorRetrievalRequest,
    VectorRetrievalResponse,
)
from spurel.retrieval.service import VectorRetrievalProviderContractError
from spurel.retrieval.trace_ports import RetrievalTracePersistenceError
from spurel.retrieval.traced import (
    TracedHybridRetrievalService,
    TracedKeywordRetrievalService,
    TracedVectorRetrievalService,
)
from spurel.retrieval.tracing import RetrievalTraceValidationError

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/retrieval",
    tags=["retrieval"],
)

HybridRetrievalServiceDependency = Annotated[
    TracedHybridRetrievalService,
    Depends(get_traced_hybrid_retrieval_service),
]

KeywordRetrievalServiceDependency = Annotated[
    TracedKeywordRetrievalService,
    Depends(get_traced_keyword_retrieval_service),
]

VectorRetrievalServiceDependency = Annotated[
    TracedVectorRetrievalService,
    Depends(get_traced_vector_retrieval_service),
]


@router.post("/vector", response_model=VectorRetrievalResponse)
async def vector_retrieval(
    knowledge_base_id: UUID,
    payload: VectorRetrievalRequest,
    service: VectorRetrievalServiceDependency,
) -> VectorRetrievalResponse:
    """Run exact vector retrieval for the Retrieval Playground."""
    try:
        execution = await service.search(
            knowledge_base_id=knowledge_base_id,
            query=payload.query,
            limit=payload.top_k,
        )
    except VectorRetrievalQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="retrieval request is invalid",
        ) from exc
    except (
        EmbeddingError,
        VectorRetrievalProviderContractError,
        VectorRetrievalRepositoryError,
        RetrievalTracePersistenceError,
        RetrievalTraceValidationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="retrieval service temporarily unavailable",
        ) from exc

    return VectorRetrievalResponse(
        trace_id=execution.trace_id,
        duration_ms=execution.duration_ms,
        query=payload.query.strip(),
        top_k=payload.top_k,
        matches=[
            VectorRetrievalMatchResponse(
                rank=rank,
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                chunk_index=match.chunk_index,
                text=match.text,
                start_offset=match.start_offset,
                end_offset=match.end_offset,
                cosine_similarity=match.cosine_similarity,
            )
            for rank, match in enumerate(execution.matches, start=1)
        ],
    )


@router.post("/keyword", response_model=KeywordRetrievalResponse)
async def keyword_retrieval(
    knowledge_base_id: UUID,
    payload: KeywordRetrievalRequest,
    service: KeywordRetrievalServiceDependency,
) -> KeywordRetrievalResponse:
    """Run PostgreSQL full-text keyword retrieval."""
    try:
        execution = await service.search(
            knowledge_base_id=knowledge_base_id,
            query=payload.query,
            limit=payload.top_k,
        )
    except KeywordRetrievalQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="retrieval request is invalid",
        ) from exc
    except (
        KeywordRetrievalRepositoryError,
        RetrievalTracePersistenceError,
        RetrievalTraceValidationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="retrieval service temporarily unavailable",
        ) from exc

    return KeywordRetrievalResponse(
        trace_id=execution.trace_id,
        duration_ms=execution.duration_ms,
        query=payload.query.strip(),
        top_k=payload.top_k,
        matches=[
            KeywordRetrievalMatchResponse(
                rank=rank,
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                chunk_index=match.chunk_index,
                text=match.text,
                start_offset=match.start_offset,
                end_offset=match.end_offset,
                keyword_score=match.keyword_score,
            )
            for rank, match in enumerate(execution.matches, start=1)
        ],
    )


@router.post("/hybrid", response_model=HybridRetrievalResponse)
async def hybrid_retrieval(
    knowledge_base_id: UUID,
    payload: HybridRetrievalRequest,
    service: HybridRetrievalServiceDependency,
) -> HybridRetrievalResponse:
    """Run vector + keyword retrieval fused with reciprocal rank fusion."""
    try:
        execution = await service.search(
            knowledge_base_id=knowledge_base_id,
            query=payload.query,
            limit=payload.top_k,
            candidate_limit=payload.candidate_k,
            rrf_k=payload.rrf_k,
        )
    except HybridRetrievalQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="retrieval request is invalid",
        ) from exc
    except (
        EmbeddingError,
        VectorRetrievalProviderContractError,
        VectorRetrievalRepositoryError,
        KeywordRetrievalRepositoryError,
        HybridRetrievalResultError,
        RetrievalTracePersistenceError,
        RetrievalTraceValidationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="retrieval service temporarily unavailable",
        ) from exc

    return HybridRetrievalResponse(
        trace_id=execution.trace_id,
        duration_ms=execution.duration_ms,
        query=payload.query.strip(),
        top_k=payload.top_k,
        candidate_k=payload.candidate_k,
        rrf_k=payload.rrf_k,
        matches=[
            HybridRetrievalMatchResponse(
                rank=rank,
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                chunk_index=match.chunk_index,
                text=match.text,
                start_offset=match.start_offset,
                end_offset=match.end_offset,
                rrf_score=match.rrf_score,
                vector_rank=match.vector_rank,
                keyword_rank=match.keyword_rank,
                cosine_similarity=match.cosine_similarity,
                keyword_score=match.keyword_score,
            )
            for rank, match in enumerate(execution.matches, start=1)
        ],
    )
