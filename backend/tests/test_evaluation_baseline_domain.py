from datetime import UTC, datetime
from uuid import uuid4

import pytest

from spurel.evaluation_datasets.baseline_domain import (
    EvaluationBaseline,
    EvaluationBaselineConfiguration,
    EvaluationBaselineConfigurationError,
)
from spurel.evaluation_datasets.execution import DatasetEvaluationMode
from spurel.evaluation_datasets.run_domain import EvaluationRun


def _run(
    *,
    mode: DatasetEvaluationMode,
    top_k: int = 10,
    candidate_k: int | None = None,
    rrf_k: int | None = None,
    embedding_model: str | None = None,
) -> EvaluationRun:
    uses_embeddings = mode is not DatasetEvaluationMode.KEYWORD
    return EvaluationRun(
        id=uuid4(),
        knowledge_base_id=uuid4(),
        dataset_id=uuid4(),
        mode=mode,
        top_k=top_k,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        embedding_provider="openai" if uses_embeddings else None,
        embedding_model=(embedding_model or "model-a") if uses_embeddings else None,
        embedding_dimensions=1536 if uses_embeddings else None,
        case_count=1,
        total_duration_ms=1.0,
        mean_duration_ms=1.0,
        judgment_coverage_case_count=1,
        mean_judgment_coverage_at_k=1.0,
        mean_precision_at_k=1.0,
        mean_recall_at_k=1.0,
        mrr_at_k=1.0,
        mean_ndcg_at_k=1.0,
        cases=(),
        created_at=datetime.now(UTC),
    )


def test_configuration_fingerprint_is_stable_for_same_exact_config() -> None:
    first = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.HYBRID,
        top_k=10,
        candidate_k=50,
        rrf_k=60,
        embedding_provider="openai",
        embedding_model="model-a",
        embedding_dimensions=1536,
    )
    second = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.HYBRID,
        top_k=10,
        candidate_k=50,
        rrf_k=60,
        embedding_provider="openai",
        embedding_model="model-a",
        embedding_dimensions=1536,
    )

    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64


def test_configuration_fingerprint_changes_with_retrieval_config() -> None:
    first = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.VECTOR,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider="openai",
        embedding_model="model-a",
        embedding_dimensions=1536,
    )
    second = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.VECTOR,
        top_k=20,
        candidate_k=None,
        rrf_k=None,
        embedding_provider="openai",
        embedding_model="model-a",
        embedding_dimensions=1536,
    )

    assert first.fingerprint != second.fingerprint


def test_baseline_from_run_captures_exact_configuration() -> None:
    run = _run(
        mode=DatasetEvaluationMode.HYBRID,
        candidate_k=50,
        rrf_k=60,
    )

    baseline = EvaluationBaseline.from_run(run=run)

    assert baseline.knowledge_base_id == run.knowledge_base_id
    assert baseline.dataset_id == run.dataset_id
    assert baseline.run_id == run.id
    assert baseline.configuration.mode is DatasetEvaluationMode.HYBRID
    assert baseline.configuration.candidate_k == 50
    assert baseline.configuration_fingerprint == baseline.configuration.fingerprint


def test_keyword_configuration_rejects_embedding_metadata() -> None:
    configuration = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.KEYWORD,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider="openai",
        embedding_model="model-a",
        embedding_dimensions=1536,
    )

    with pytest.raises(EvaluationBaselineConfigurationError):
        configuration.validate()


def test_hybrid_configuration_requires_candidate_and_rrf_settings() -> None:
    configuration = EvaluationBaselineConfiguration(
        mode=DatasetEvaluationMode.HYBRID,
        top_k=10,
        candidate_k=None,
        rrf_k=None,
        embedding_provider="openai",
        embedding_model="model-a",
        embedding_dimensions=1536,
    )

    with pytest.raises(EvaluationBaselineConfigurationError):
        configuration.validate()
