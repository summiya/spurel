"""FastAPI boundary for grounded RAG answers."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from spurel.embeddings.domain import EmbeddingError
from spurel.generation.domain import TextGenerationResultError
from spurel.generation.ports import TextGenerationProviderError
from spurel.rag.dependencies import get_rag_answer_service
from spurel.rag.schemas import RAGAnswerRequest, RAGAnswerResponse
from spurel.rag.service import RAGAnswerService, RAGContextError
from spurel.retrieval.hybrid import (
    HybridRetrievalQueryError,
    HybridRetrievalResultError,
)
from spurel.retrieval.keyword_ports import KeywordRetrievalRepositoryError
from spurel.retrieval.ports import VectorRetrievalRepositoryError
from spurel.retrieval.service import VectorRetrievalProviderContractError
from spurel.retrieval.trace_ports import RetrievalTracePersistenceError
from spurel.retrieval.tracing import RetrievalTraceValidationError

router = APIRouter(
    prefix="/knowledge-bases/{knowledge_base_id}/rag",
    tags=["rag"],
)

RAGAnswerServiceDependency = Annotated[
    RAGAnswerService,
    Depends(get_rag_answer_service),
]


@router.post("/answer", response_model=RAGAnswerResponse)
async def answer_with_rag(
    knowledge_base_id: UUID,
    payload: RAGAnswerRequest,
    service: RAGAnswerServiceDependency,
) -> RAGAnswerResponse:
    """Generate one answer grounded in retrieved knowledge-base chunks."""
    try:
        result = await service.answer(
            knowledge_base_id=knowledge_base_id,
            query=payload.query,
            top_k=payload.top_k,
            candidate_k=payload.candidate_k,
            rrf_k=payload.rrf_k,
        )
    except (RAGContextError, HybridRetrievalQueryError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="RAG request is invalid",
        ) from exc
    except (
        EmbeddingError,
        HybridRetrievalResultError,
        KeywordRetrievalRepositoryError,
        VectorRetrievalProviderContractError,
        VectorRetrievalRepositoryError,
        RetrievalTracePersistenceError,
        RetrievalTraceValidationError,
        TextGenerationProviderError,
        TextGenerationResultError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service temporarily unavailable",
        ) from exc

    return RAGAnswerResponse(
        trace_id=result.trace_id,
        answer=result.answer,
        retrieved_chunk_count=result.retrieved_chunk_count,
        generation_provider=result.generation_provider,
        generation_model=result.generation_model,
    )
