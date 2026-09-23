"""FastAPI boundary for the Retrieval Playground."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from spurel.embeddings.domain import EmbeddingError
from spurel.retrieval.dependencies import (
    get_keyword_retrieval_service,
    get_vector_retrieval_service,
)
from spurel.retrieval.domain import VectorRetrievalQueryError
from spurel.retrieval.keyword_domain import KeywordRetrievalQueryError
from spurel.retrieval.keyword_ports import KeywordRetrievalRepositoryError
from spurel.retrieval.keyword_service import KeywordRetrievalService
from spurel.retrieval.ports import VectorRetrievalRepositoryError
from spurel.retrieval.schemas import (
    KeywordRetrievalMatchResponse,
    KeywordRetrievalRequest,
    KeywordRetrievalResponse,
    VectorRetrievalMatchResponse,
    VectorRetrievalRequest,
    VectorRetrievalResponse,
)
from spurel.retrieval.service import (
    VectorRetrievalProviderContractError,
    VectorRetrievalService,
)

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/retrieval",
    tags=["retrieval"],
)

KeywordRetrievalServiceDependency = Annotated[
    KeywordRetrievalService,
    Depends(get_keyword_retrieval_service),
]

VectorRetrievalServiceDependency = Annotated[
    VectorRetrievalService,
    Depends(get_vector_retrieval_service),
]


@router.post("/vector", response_model=VectorRetrievalResponse)
async def vector_retrieval(
    knowledge_base_id: UUID,
    payload: VectorRetrievalRequest,
    service: VectorRetrievalServiceDependency,
) -> VectorRetrievalResponse:
    """Run exact vector retrieval for the Retrieval Playground."""
    try:
        matches = await service.search(
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
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="retrieval service temporarily unavailable",
        ) from exc

    return VectorRetrievalResponse(
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
            for rank, match in enumerate(matches, start=1)
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
        matches = await service.search(
            knowledge_base_id=knowledge_base_id,
            query=payload.query,
            limit=payload.top_k,
        )
    except KeywordRetrievalQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="retrieval request is invalid",
        ) from exc
    except KeywordRetrievalRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="retrieval service temporarily unavailable",
        ) from exc

    return KeywordRetrievalResponse(
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
            for rank, match in enumerate(matches, start=1)
        ],
    )
