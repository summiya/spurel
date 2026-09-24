"""Dependency wiring for evaluation datasets."""

from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from openai import AsyncOpenAI

from spurel.db import async_session_factory
from spurel.embeddings.config import (
    EmbeddingConfigurationError,
    OpenAIEmbeddingConfig,
)
from spurel.evaluation_datasets.baseline_service import EvaluationBaselineService
from spurel.evaluation_datasets.execution import (
    DatasetEvaluationExecutionService,
    DatasetEvaluationMode,
    HybridDatasetRetriever,
    KeywordDatasetRetriever,
    VectorDatasetRetriever,
)
from spurel.evaluation_datasets.quality_gate import EvaluationQualityGateService
from spurel.evaluation_datasets.run_comparison import (
    EvaluationRunComparisonService,
)
from spurel.evaluation_datasets.run_service import (
    EvaluationRunService,
    PersistedDatasetEvaluationService,
)
from spurel.evaluation_datasets.service import EvaluationDatasetService
from spurel.evaluation_datasets.sqlalchemy_baseline_repository import (
    SqlAlchemyEvaluationBaselineRepository,
)
from spurel.evaluation_datasets.sqlalchemy_repository import (
    SqlAlchemyEvaluationDatasetRepository,
)
from spurel.evaluation_datasets.sqlalchemy_run_repository import (
    SqlAlchemyEvaluationRunRepository,
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


def get_evaluation_run_service() -> EvaluationRunService:
    """Build durable benchmark run history."""
    return EvaluationRunService(
        SqlAlchemyEvaluationRunRepository(async_session_factory)
    )


def get_keyword_dataset_evaluation_service() -> PersistedDatasetEvaluationService:
    """Build keyword-only dataset evaluation without provider credentials."""
    repository = SqlAlchemyEvaluationDatasetRepository(async_session_factory)
    keyword_retriever = KeywordRetrievalService(
        SqlAlchemyKeywordRetrievalRepository(async_session_factory)
    )

    executor = DatasetEvaluationExecutionService(
        repository=repository,
        retriever=KeywordDatasetRetriever(keyword_retriever),
        mode=DatasetEvaluationMode.KEYWORD,
    )
    return PersistedDatasetEvaluationService(
        executor=executor,
        runs=get_evaluation_run_service(),
    )


async def get_vector_dataset_evaluation_service() -> AsyncIterator[
    PersistedDatasetEvaluationService
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

        executor = DatasetEvaluationExecutionService(
            repository=SqlAlchemyEvaluationDatasetRepository(
                async_session_factory
            ),
            retriever=VectorDatasetRetriever(vector_retriever),
            mode=DatasetEvaluationMode.VECTOR,
            embedding_provider=provider.provider,
            embedding_model=provider.model,
            embedding_dimensions=provider.dimensions,
        )
        yield PersistedDatasetEvaluationService(
            executor=executor,
            runs=get_evaluation_run_service(),
        )
    finally:
        await client.close()


async def get_hybrid_dataset_evaluation_service() -> AsyncIterator[
    PersistedDatasetEvaluationService
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

        executor = DatasetEvaluationExecutionService(
            repository=SqlAlchemyEvaluationDatasetRepository(
                async_session_factory
            ),
            retriever=HybridDatasetRetriever(hybrid_retriever),
            mode=DatasetEvaluationMode.HYBRID,
            embedding_provider=provider.provider,
            embedding_model=provider.model,
            embedding_dimensions=provider.dimensions,
        )
        yield PersistedDatasetEvaluationService(
            executor=executor,
            runs=get_evaluation_run_service(),
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


def get_evaluation_run_comparison_service() -> EvaluationRunComparisonService:
    """Build descriptive persisted benchmark comparison."""
    return EvaluationRunComparisonService(get_evaluation_run_service())


def get_evaluation_quality_gate_service() -> EvaluationQualityGateService:
    """Build explicit threshold-based benchmark quality gates."""
    return EvaluationQualityGateService(
        get_evaluation_run_comparison_service()
    )



def get_evaluation_baseline_service() -> EvaluationBaselineService:
    """Build explicit promoted evaluation baseline management."""
    return EvaluationBaselineService(
        repository=SqlAlchemyEvaluationBaselineRepository(async_session_factory),
        runs=get_evaluation_run_service(),
    )
