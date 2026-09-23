"""Dependency wiring for vector retrieval."""

from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from openai import AsyncOpenAI

from spurel.db import async_session_factory
from spurel.embeddings.config import (
    EmbeddingConfigurationError,
    OpenAIEmbeddingConfig,
)
from spurel.infrastructure.embeddings import OpenAIEmbeddingProvider
from spurel.retrieval.service import VectorRetrievalService
from spurel.retrieval.sqlalchemy_repository import (
    SqlAlchemyVectorRetrievalRepository,
)


async def get_vector_retrieval_service() -> AsyncIterator[VectorRetrievalService]:
    """Build and safely dispose the configured vector retrieval service."""
    try:
        config = OpenAIEmbeddingConfig.from_env()
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="retrieval service temporarily unavailable",
        ) from exc

    client = AsyncOpenAI(api_key=config.api_key)

    try:
        provider = OpenAIEmbeddingProvider(
            client=client,
            model=config.model,
            dimensions=config.dimensions,
        )
        repository = SqlAlchemyVectorRetrievalRepository(async_session_factory)

        yield VectorRetrievalService(
            provider=provider,
            repository=repository,
        )
    finally:
        await client.close()
