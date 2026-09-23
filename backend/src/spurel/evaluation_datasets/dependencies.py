"""Dependency wiring for evaluation datasets."""

from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from openai import AsyncOpenAI

from spurel.db import async_session_factory
from spurel.embeddings.config import (
    EmbeddingConfigurationError,
    OpenAIEmbeddingConfig,
)
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationExecutionService,
    DatasetEvaluationMode,
    HybridDatasetRetriever,
    KeywordDatasetRetriever,
    VectorDatasetRetriever,
)
from spurel.evaluation_datasets.service import EvaluationDatasetService
from spurel.evaluation_datasets.sqlalchemy_repository import (
    SqlAlchemyEvaluationDatasetRepository,
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


def get_evaluation_dataset_service() -> EvaluationDatasetService:
    """Build reusable evaluation dataset services."""
    return EvaluationDatasetService(
        SqlAlchemyEvaluationDatasetRepository(async_session_factory)
    )


def get_keyword_dataset_evaluation_service() -> DatasetEvaluationExecutionService:
    """Build keyword-only dataset evaluation without provider credentials."""
    repository = SqlAlchemyEvaluationDatasetRepository(async_session_factory)
    keyword_retriever = KeywordRetrievalService(
        SqlAlchemyKeywordRetrievalRepository(async_session_factory)
    )

    return DatasetEvaluationExecutionService(
        repository=repository,
        retriever=KeywordDatasetRetriever(keyword_retriever),
        mode=DatasetEvaluationMode.KEYWORD,
    )


async def get_vector_dataset_evaluation_service() -> AsyncIterator[
    DatasetEvaluationExecutionService
]:
    """Build vector dataset evaluation with safe provider lifecycle."""
    config = _load_embedding_config()
    client = AsyncOpenAI(api_key=config.api_key)

    try:
        provider = OpenAIEmbeddingProvider(
            client=client,
            model=config.model,
            dimensions=config.dimensions,
        )
        vector_retriever = VectorRetrievalService(
            provider=provider,
            repository=SqlAlchemyVectorRetrievalRepository(
                async_session_factory
            ),
        )

        yield DatasetEvaluationExecutionService(
            repository=SqlAlchemyEvaluationDatasetRepository(
                async_session_factory
            ),
            retriever=VectorDatasetRetriever(vector_retriever),
            mode=DatasetEvaluationMode.VECTOR,
            embedding_provider=provider.provider,
            embedding_model=provider.model,
            embedding_dimensions=provider.dimensions,
        )
    finally:
        await client.close()


async def get_hybrid_dataset_evaluation_service() -> AsyncIterator[
    DatasetEvaluationExecutionService
]:
    """Build hybrid dataset evaluation with safe provider lifecycle."""
    config = _load_embedding_config()
    client = AsyncOpenAI(api_key=config.api_key)

    try:
        provider = OpenAIEmbeddingProvider(
            client=client,
            model=config.model,
            dimensions=config.dimensions,
        )
        vector_retriever = VectorRetrievalService(
            provider=provider,
            repository=SqlAlchemyVectorRetrievalRepository(
                async_session_factory
            ),
        )
        keyword_retriever = KeywordRetrievalService(
            SqlAlchemyKeywordRetrievalRepository(async_session_factory)
        )
        hybrid_retriever = HybridRetrievalService(
            vector_retriever=vector_retriever,
            keyword_retriever=keyword_retriever,
        )

        yield DatasetEvaluationExecutionService(
            repository=SqlAlchemyEvaluationDatasetRepository(
                async_session_factory
            ),
            retriever=HybridDatasetRetriever(hybrid_retriever),
            mode=DatasetEvaluationMode.HYBRID,
            embedding_provider=provider.provider,
            embedding_model=provider.model,
            embedding_dimensions=provider.dimensions,
        )
    finally:
        await client.close()


def _load_embedding_config() -> OpenAIEmbeddingConfig:
    try:
        return OpenAIEmbeddingConfig.from_env()
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dataset evaluation service temporarily unavailable",
        ) from exc
