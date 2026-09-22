"""Application-facing persistence ports for knowledge bases."""

from collections.abc import Sequence
from typing import Protocol

from spurel.knowledge_bases.domain import KnowledgeBase


class KnowledgeBasePersistenceError(RuntimeError):
    """Raised when knowledge base persistence cannot complete."""


class KnowledgeBaseRepository(Protocol):
    """Persistence contract used by knowledge base application services."""

    async def add(self, knowledge_base: KnowledgeBase) -> None:
        """Persist a knowledge base."""
        ...

    async def list(self) -> Sequence[KnowledgeBase]:
        """Return knowledge bases in deterministic creation order."""
        ...
