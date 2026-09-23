from spurel.evaluation_datasets.persistence import (
    EvaluationCaseRecord,
    EvaluationDatasetRecord,
    EvaluationJudgmentRecord,
)


def test_judgment_chunk_identity_is_not_foreign_keyed_to_live_chunks() -> None:
    assert list(EvaluationJudgmentRecord.__table__.c.chunk_id.foreign_keys) == []


def test_dataset_and_case_history_indexes_exist() -> None:
    dataset_index = next(
        index
        for index in EvaluationDatasetRecord.__table__.indexes
        if index.name == "ix_evaluation_datasets_knowledge_base_created_id"
    )
    case_index = next(
        index
        for index in EvaluationCaseRecord.__table__.indexes
        if index.name == "ix_evaluation_cases_dataset_created_id"
    )

    assert [column.name for column in dataset_index.columns] == [
        "knowledge_base_id",
        "created_at",
        "id",
    ]
    assert [column.name for column in case_index.columns] == [
        "dataset_id",
        "created_at",
        "id",
    ]


def test_case_judgments_are_unique_per_chunk() -> None:
    constraint_names = {
        constraint.name
        for constraint in EvaluationJudgmentRecord.__table__.constraints
    }

    assert "uq_evaluation_judgments_case_chunk" in constraint_names
