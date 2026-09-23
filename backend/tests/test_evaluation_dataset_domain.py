from uuid import uuid4

import pytest

from spurel.evaluation_datasets.domain import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationDatasetValidationError,
)
from spurel.retrieval.evaluation import RelevanceJudgment


def test_dataset_and_case_creation_normalize_input() -> None:
    knowledge_base_id = uuid4()
    dataset = EvaluationDataset.create(
        knowledge_base_id=knowledge_base_id,
        name="  Baseline set  ",
    )
    relevant = RelevanceJudgment(chunk_id=uuid4(), relevance=3)
    non_relevant = RelevanceJudgment(chunk_id=uuid4(), relevance=0)

    case = EvaluationCase.create(
        dataset_id=dataset.id,
        query="  authentication architecture  ",
        judgments=(relevant, non_relevant),
    )

    assert dataset.name == "Baseline set"
    assert dataset.knowledge_base_id == knowledge_base_id
    assert case.query == "authentication architecture"
    assert case.dataset_id == dataset.id
    assert case.judgments == (relevant, non_relevant)


def test_case_rejects_duplicate_chunk_judgments() -> None:
    chunk_id = uuid4()

    with pytest.raises(EvaluationDatasetValidationError):
        EvaluationCase.create(
            dataset_id=uuid4(),
            query="query",
            judgments=(
                RelevanceJudgment(chunk_id=chunk_id, relevance=1),
                RelevanceJudgment(chunk_id=chunk_id, relevance=2),
            ),
        )


def test_case_requires_at_least_one_relevant_judgment() -> None:
    with pytest.raises(EvaluationDatasetValidationError):
        EvaluationCase.create(
            dataset_id=uuid4(),
            query="query",
            judgments=(
                RelevanceJudgment(chunk_id=uuid4(), relevance=0),
            ),
        )
