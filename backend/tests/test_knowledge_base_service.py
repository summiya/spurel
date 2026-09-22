import asyncio
from collections.abc import Sequence

from spurel.knowledge_bases.domain import KnowledgeBase
from spurel.knowledge_bases.service import KnowledgeBaseService


class FakeKnowledgeBaseRepository:
    def __init__(self) -> None:
        self.items: list[KnowledgeBase] = []

    async def add(self, knowledge_base: KnowledgeBase) -> None:
        self.items.append(knowledge_base)

    async def list(self, *, limit: int, offset: int) -> Sequence[KnowledgeBase]:
        return tuple(self.items[offset : offset + limit])


def test_create_knowledge_base_through_service() -> None:
    repository = FakeKnowledgeBaseRepository()
    service = KnowledgeBaseService(repository)

    created = asyncio.run(service.create("  Engineering Docs  "))

    assert created.name == "Engineering Docs"
    assert repository.items == [created]


def test_list_knowledge_bases_through_service() -> None:
    repository = FakeKnowledgeBaseRepository()
    first = KnowledgeBase.create("Engineering Docs")
    second = KnowledgeBase.create("Product Docs")
    repository.items.extend([first, second])
    service = KnowledgeBaseService(repository)

    result = asyncio.run(service.list(limit=1, offset=1))

    assert tuple(result) == (second,)
