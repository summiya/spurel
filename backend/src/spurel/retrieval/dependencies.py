"""Dependency wiring for vector retrieval."""

from openai import AsyncOpenAI

from spurel.db import async_session_factory
from spurel.embeddings.config import OpenAIEmbeddingConfig
from spurel.infrastructure.embeddings import OpenAIEmbeddingProvider
from spurel.retrieval.service import VectorRetrievalService
from spurel.retrieval.sqlalchemy_repository import (
    SqlAlchemyVectorRetrievalRepository,
)


def get_vector_retrieval_service() -> VectorRetrievalService:
    """Build the configured exact-vector retrieval service."""
    config = OpenAIEmbeddingConfig.from_env()

    client = AsyncOpenAI(api_key=config.api_key)
    provider = OpenAIEmbeddingProvider(
        client=client,
        model=config.model,
        dimensions=config.dimensions,
    )
    repository = SqlAlchemyVectorRetrievalRepository(async_session_factory)

    return VectorRetrievalService(
        provider=provider,
        repository=repository,
    )
