"""Contracts for bounded judgment audits and safe history reporting."""

from uuid import uuid4

from spurel.evaluation_datasets.judgment_integrity import (
    EvaluationJudgmentAudit,
    EvaluationJudgmentIssue,
    EvaluationJudgmentIssueReason,
)


def test_audit_counts_all_invalid_labels_without_discarding_historical_data() -> None:
    issues = (
        EvaluationJudgmentIssue(
            case_id=uuid4(),
            chunk_id=uuid4(),
            reason=EvaluationJudgmentIssueReason.INACTIVE_VERSION,
            document_id=uuid4(),
            chunk_version=1,
            active_chunk_version=2,
        ),
    )
    audit = EvaluationJudgmentAudit(
        dataset_id=uuid4(),
        case_count=2,
        judgment_count=103,
        inactive_version_count=101,
        missing_or_out_of_scope_count=1,
        issues=issues,
    )

    assert not audit.is_usable
    assert audit.invalid_count == 102
    assert audit.issues_truncated


def test_empty_valid_audit_is_usable() -> None:
    audit = EvaluationJudgmentAudit(
        dataset_id=uuid4(),
        case_count=0,
        judgment_count=0,
        inactive_version_count=0,
        missing_or_out_of_scope_count=0,
        issues=(),
    )
    assert audit.is_usable
    assert not audit.issues_truncated
