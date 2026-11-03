"""Read-only validity audit for version-aware evaluation relevance judgments.

Historical labels are immutable and may refer to inactive or deleted chunks.
A dataset is usable for live benchmarks only if every label references an
active chunk from its own knowledge base.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

MAX_JUDGMENT_AUDIT_ISSUES = 100


class EvaluationJudgmentIssueReason(StrEnum):
    """Why a historical relevance judgment cannot score the active index."""

    INACTIVE_VERSION = "inactive_version"
    MISSING_OR_OUT_OF_SCOPE = "missing_or_out_of_scope"


@dataclass(frozen=True, slots=True)
class EvaluationJudgmentIssue:
    """One problematic label, safe to expose within its dataset scope."""

    case_id: UUID
    chunk_id: UUID
    reason: EvaluationJudgmentIssueReason
    document_id: UUID | None = None
    chunk_version: int | None = None
    active_chunk_version: int | None = None


@dataclass(frozen=True, slots=True)
class EvaluationJudgmentAudit:
    """Counts all issues and returns a bounded ordered set for remediation."""

    dataset_id: UUID
    case_count: int
    judgment_count: int
    inactive_version_count: int
    missing_or_out_of_scope_count: int
    issues: tuple[EvaluationJudgmentIssue, ...]

    @property
    def invalid_count(self) -> int:
        """Total labels that cannot be scored against the current active index."""
        return self.inactive_version_count + self.missing_or_out_of_scope_count

    @property
    def is_usable(self) -> bool:
        """Whether the labels can safely score the current active index."""
        return self.invalid_count == 0

    @property
    def issues_truncated(self) -> bool:
        """Whether the report omits extra issue details after the sample limit."""
        return self.invalid_count > len(self.issues)
