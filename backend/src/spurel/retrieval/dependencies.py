"""Dependency wiring for Retrieval Playground services."""

from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from openai import AsyncOpenAI

from spurel.db import async_session_factory
from spurel.embeddings.config import (
    EmbeddingConfigurationError,
    OpenAIEmbeddingConfig,
)
from spurel.infrastructure.embeddings import OpenAIEmbeddingProvider
from spurel.retrieval.hybrid import HybridRetrievalService
from spurel.retrieval.keyword_service import KeywordRetrievalService
from spurel.retrieval.service import VectorRetrievalService
from spurel.retrieval.sqlalchemy_keyword_repository import (
    SqlAlchemyKeywordRetrievalRepository,
)
from spurel.retrieval.sqlalchemy_repository import (
    SqlAlchemyVectorRetrievalRepository,
)
from spurel.retrieval.sqlalchemy_trace_repository import (
    SqlAlchemyRetrievalTraceRepository,
)
from spurel.retrieval.trace_service import RetrievalTraceService
from spurel.retrieval.traced import (
    TracedHybridRetrievalService,
    TracedKeywordRetrievalService,
    TracedVectorRetrievalService,
)


def get_keyword_retrieval_service() -> KeywordRetrievalService:
    """Build the PostgreSQL keyword retrieval service."""
    repository = SqlAlchemyKeywordRetrievalRepository(async_session_factory)
    return KeywordRetrievalService(repository)


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


async def get_hybrid_retrieval_service() -> AsyncIterator[HybridRetrievalService]:
    """Build and safely dispose vector + keyword hybrid retrieval."""
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
        vector_service = VectorRetrievalService(
            provider=provider,
            repository=SqlAlchemyVectorRetrievalRepository(
                async_session_factory
            ),
        )
        keyword_service = KeywordRetrievalService(
            SqlAlchemyKeywordRetrievalRepository(async_session_factory)
        )

        yield HybridRetrievalService(
            vector_retriever=vector_service,
            keyword_retriever=keyword_service,
        )
    finally:
        await client.close()


def get_retrieval_trace_service() -> RetrievalTraceService:
    """Build durable retrieval trace persistence."""
    return RetrievalTraceService(
        SqlAlchemyRetrievalTraceRepository(async_session_factory)
    )


def get_traced_keyword_retrieval_service() -> TracedKeywordRetrievalService:
    """Build keyword retrieval with mandatory durable tracing."""
    return TracedKeywordRetrievalService(
        retriever=get_keyword_retrieval_service(),
        trace_service=get_retrieval_trace_service(),
    )


async def get_traced_vector_retrieval_service() -> AsyncIterator[
    TracedVectorRetrievalService
]:
    """Build vector retrieval with mandatory durable tracing."""
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
        retriever = VectorRetrievalService(
            provider=provider,
            repository=SqlAlchemyVectorRetrievalRepository(
                async_session_factory
            ),
        )

        yield TracedVectorRetrievalService(
            retriever=retriever,
            trace_service=get_retrieval_trace_service(),
            embedding_provider=provider.provider,
            embedding_model=provider.model,
            embedding_dimensions=provider.dimensions,
        )
    finally:
        await client.close()


async def get_traced_hybrid_retrieval_service() -> AsyncIterator[
    TracedHybridRetrievalService
]:
    """Build hybrid retrieval with mandatory durable tracing."""
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
        vector_service = VectorRetrievalService(
            provider=provider,
            repository=SqlAlchemyVectorRetrievalRepository(
                async_session_factory
            ),
        )
        keyword_service = KeywordRetrievalService(
            SqlAlchemyKeywordRetrievalRepository(async_session_factory)
        )
        retriever = HybridRetrievalService(
            vector_retriever=vector_service,
            keyword_retriever=keyword_service,
        )

        yield TracedHybridRetrievalService(
            retriever=retriever,
            trace_service=get_retrieval_trace_service(),
            embedding_provider=provider.provider,
            embedding_model=provider.model,
            embedding_dimensions=provider.dimensions,
        )
    finally:
        await client.close()
