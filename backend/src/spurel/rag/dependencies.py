"""Dependency wiring for retrieval-augmented answer generation."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from openai import AsyncOpenAI

from spurel.generation.config import (
    GenerationConfigurationError,
    OpenAIGenerationConfig,
)
from spurel.infrastructure.generation import OpenAITextGenerationProvider
from spurel.rag.service import RAGAnswerService
from spurel.retrieval.dependencies import get_traced_hybrid_retrieval_service
from spurel.retrieval.traced import TracedHybridRetrievalService

TracedHybridRetrievalDependency = Annotated[
    TracedHybridRetrievalService,
    Depends(get_traced_hybrid_retrieval_service),
]


async def get_rag_answer_service(
    retriever: TracedHybridRetrievalDependency,
) -> AsyncIterator[RAGAnswerService]:
    """Build grounded RAG generation with independent provider lifecycle."""
    try:
        config = OpenAIGenerationConfig.from_env()
    except GenerationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service temporarily unavailable",
        ) from exc

    client = AsyncOpenAI(api_key=config.api_key)
    try:
        generator = OpenAITextGenerationProvider(
            client=client,
            model=config.model,
            max_output_tokens=config.max_output_tokens,
        )
        yield RAGAnswerService(
            retriever=retriever,
            generator=generator,
        )
    finally:
        await client.close()
