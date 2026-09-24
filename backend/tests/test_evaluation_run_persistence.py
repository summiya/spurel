from spurel.evaluation_datasets.run_persistence import (
    EvaluationRunCaseRecord,
    EvaluationRunRecord,
)


def test_run_dataset_identity_is_historical_not_cascading() -> None:
    assert list(EvaluationRunRecord.__table__.c.dataset_id.foreign_keys) == []


def test_run_case_identity_is_historical_not_cascading() -> None:
    assert list(EvaluationRunCaseRecord.__table__.c.case_id.foreign_keys) == []


def test_run_history_and_case_order_indexes_exist() -> None:
    run_index = next(
        index
        for index in EvaluationRunRecord.__table__.indexes
        if index.name == "ix_evaluation_runs_kb_dataset_created_id"
    )
    case_index = next(
        index
        for index in EvaluationRunCaseRecord.__table__.indexes
        if index.name == "ix_evaluation_run_cases_run_position"
    )

    assert [column.name for column in run_index.columns] == [
        "knowledge_base_id",
        "dataset_id",
        "created_at",
        "id",
    ]
    assert [column.name for column in case_index.columns] == [
        "run_id",
        "position",
    ]


def test_run_case_position_and_case_identity_are_unique_per_run() -> None:
    constraint_names = {
        constraint.name
        for constraint in EvaluationRunCaseRecord.__table__.constraints
    }

    assert "uq_evaluation_run_cases_run_position" in constraint_names
    assert "uq_evaluation_run_cases_run_case" in constraint_names
