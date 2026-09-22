from collections.abc import Sequence

from fastapi.testclient import TestClient

from spurel.knowledge_bases.dependencies import get_knowledge_base_service
from spurel.knowledge_bases.domain import KnowledgeBase
from spurel.knowledge_bases.ports import KnowledgeBasePersistenceError
from spurel.knowledge_bases.service import KnowledgeBaseService
from spurel.main import create_app


class FakeKnowledgeBaseRepository:
    def __init__(self) -> None:
        self.items: list[KnowledgeBase] = []
        self.fail = False

    async def add(self, knowledge_base: KnowledgeBase) -> None:
        if self.fail:
            raise KnowledgeBasePersistenceError("database details must stay internal")
        self.items.append(knowledge_base)

    async def list(self, *, limit: int, offset: int) -> Sequence[KnowledgeBase]:
        if self.fail:
            raise KnowledgeBasePersistenceError("database details must stay internal")
        return tuple(self.items[offset : offset + limit])


def _client(repository: FakeKnowledgeBaseRepository) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_knowledge_base_service] = lambda: KnowledgeBaseService(
        repository
    )
    return TestClient(application)


def test_create_knowledge_base() -> None:
    repository = FakeKnowledgeBaseRepository()
    client = _client(repository)

    response = client.post("/knowledge-bases", json={"name": "Engineering Docs"})

    assert response.status_code == 201
    assert response.json()["name"] == "Engineering Docs"
    assert len(repository.items) == 1


def test_create_rejects_name_above_public_limit() -> None:
    client = _client(FakeKnowledgeBaseRepository())

    response = client.post("/knowledge-bases", json={"name": "x" * 121})

    assert response.status_code == 422


def test_list_is_bounded_and_paginated() -> None:
    repository = FakeKnowledgeBaseRepository()
    repository.items.extend(
        [
            KnowledgeBase.create("One"),
            KnowledgeBase.create("Two"),
            KnowledgeBase.create("Three"),
        ]
    )
    client = _client(repository)

    response = client.get("/knowledge-bases?limit=1&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body["items"]] == ["Two"]
    assert body["limit"] == 1
    assert body["offset"] == 1


def test_list_rejects_excessive_limit() -> None:
    client = _client(FakeKnowledgeBaseRepository())

    response = client.get("/knowledge-bases?limit=101")

    assert response.status_code == 422


def test_persistence_error_does_not_leak_internal_details() -> None:
    repository = FakeKnowledgeBaseRepository()
    repository.fail = True
    client = _client(repository)

    response = client.get("/knowledge-bases")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "knowledge base service temporarily unavailable"
    }
    assert "database details" not in response.text
