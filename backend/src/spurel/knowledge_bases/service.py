"""Application services for knowledge bases."""

from collections.abc import Sequence

from spurel.knowledge_bases.domain import KnowledgeBase
from spurel.knowledge_bases.ports import KnowledgeBaseRepository


class KnowledgeBaseService:
    """Coordinate knowledge base use cases through an abstract repository."""

    def __init__(self, repository: KnowledgeBaseRepository) -> None:
        self._repository = repository

    async def create(self, name: str) -> KnowledgeBase:
        """Create and persist a knowledge base."""
        knowledge_base = KnowledgeBase.create(name)
        await self._repository.add(knowledge_base)
        return knowledge_base

    async def list(self) -> Sequence[KnowledgeBase]:
        """List persisted knowledge bases."""
        return await self._repository.list()
