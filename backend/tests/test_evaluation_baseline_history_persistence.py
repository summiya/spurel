from spurel.evaluation_datasets.baseline_persistence import (
    EvaluationBaselinePromotionRecord,
)


def test_promotion_history_does_not_depend_on_live_baseline_or_run_rows() -> None:
    baseline_targets = {
        foreign_key.target_fullname
        for foreign_key in (
            EvaluationBaselinePromotionRecord.__table__.c.baseline_id.foreign_keys
        )
    }
    run_targets = {
        foreign_key.target_fullname
        for foreign_key in (
            EvaluationBaselinePromotionRecord.__table__.c.run_id.foreign_keys
        )
    }

    assert baseline_targets == set()
    assert run_targets == set()


def test_promotion_history_keeps_dataset_scope_foreign_keys() -> None:
    knowledge_base_targets = {
        foreign_key.target_fullname
        for foreign_key in (
            EvaluationBaselinePromotionRecord.__table__
            .c.knowledge_base_id.foreign_keys
        )
    }
    dataset_targets = {
        foreign_key.target_fullname
        for foreign_key in (
            EvaluationBaselinePromotionRecord.__table__.c.dataset_id.foreign_keys
        )
    }

    assert knowledge_base_targets == {"knowledge_bases.id"}
    assert dataset_targets == {"evaluation_datasets.id"}


def test_promotion_history_indexes_support_dataset_and_config_reads() -> None:
    indexes = {
        index.name: [column.name for column in index.columns]
        for index in EvaluationBaselinePromotionRecord.__table__.indexes
    }

    assert indexes[
        "ix_evaluation_baseline_promotions_kb_dataset_promoted_id"
    ] == [
        "knowledge_base_id",
        "dataset_id",
        "promoted_at",
        "id",
    ]
    assert indexes[
        "ix_evaluation_baseline_promotions_dataset_config_promoted_id"
    ] == [
        "knowledge_base_id",
        "dataset_id",
        "configuration_fingerprint",
        "promoted_at",
        "id",
    ]
