from spurel.evaluation_datasets.baseline_persistence import (
    EvaluationBaselineRecord,
)


def test_baseline_configuration_is_unique_per_dataset_scope() -> None:
    constraint_names = {
        constraint.name
        for constraint in EvaluationBaselineRecord.__table__.constraints
    }

    assert "uq_evaluation_baselines_dataset_config" in constraint_names


def test_baseline_keeps_real_dataset_and_run_foreign_keys() -> None:
    dataset_targets = {
        foreign_key.target_fullname
        for foreign_key in EvaluationBaselineRecord.__table__.c.dataset_id.foreign_keys
    }
    run_targets = {
        foreign_key.target_fullname
        for foreign_key in EvaluationBaselineRecord.__table__.c.run_id.foreign_keys
    }

    assert dataset_targets == {"evaluation_datasets.id"}
    assert run_targets == {"evaluation_runs.id"}


def test_baseline_history_index_supports_dataset_listing() -> None:
    index = next(
        index
        for index in EvaluationBaselineRecord.__table__.indexes
        if index.name == "ix_evaluation_baselines_kb_dataset_promoted_id"
    )

    assert [column.name for column in index.columns] == [
        "knowledge_base_id",
        "dataset_id",
        "promoted_at",
        "id",
    ]
