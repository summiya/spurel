"""Knowledge base domain model."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


class KnowledgeBaseNameError(ValueError):
    """Raised when a knowledge base name is empty."""


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    """A logical collection of documents used for retrieval."""

    id: UUID
    name: str
    created_at: datetime

    @classmethod
    def create(cls, name: str) -> "KnowledgeBase":
        """Create a knowledge base with normalized domain defaults."""
        normalized_name = name.strip()
        if not normalized_name:
            raise KnowledgeBaseNameError("knowledge base name must not be empty")

        return cls(
            id=uuid4(),
            name=normalized_name,
            created_at=datetime.now(UTC),
        )
