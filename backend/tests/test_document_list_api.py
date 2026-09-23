from collections.abc import Sequence
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.documents.dependencies import get_document_service
from spurel.documents.domain import Document
from spurel.documents.ports import DocumentPersistenceError
from spurel.documents.service import DocumentService
from spurel.main import create_app


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.items: list[Document] = []
        self.fail = False

    async def add(self, document: Document) -> None:
        self.items.append(document)

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        if self.fail:
            raise DocumentPersistenceError("database details must stay internal")

        matches = [
            document
            for document in self.items
            if document.knowledge_base_id == knowledge_base_id
        ]
        return tuple(matches[offset : offset + limit])


def _client(repository: FakeDocumentRepository) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_document_service] = lambda: DocumentService(
        repository
    )
    return TestClient(application)


def test_list_documents_is_scoped_and_paginated() -> None:
    repository = FakeDocumentRepository()
    first_knowledge_base_id = uuid4()
    second_knowledge_base_id = uuid4()

    repository.items.extend(
        [
            Document.create(
                knowledge_base_id=first_knowledge_base_id,
                filename="one.txt",
                media_type="text/plain",
                size_bytes=10,
            ),
            Document.create(
                knowledge_base_id=first_knowledge_base_id,
                filename="two.txt",
                media_type="text/plain",
                size_bytes=20,
            ),
            Document.create(
                knowledge_base_id=second_knowledge_base_id,
                filename="other.txt",
                media_type="text/plain",
                size_bytes=30,
            ),
        ]
    )

    client = _client(repository)

    response = client.get(
        f"/knowledge-bases/{first_knowledge_base_id}/documents?limit=1&offset=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["filename"] for item in body["items"]] == ["two.txt"]
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert "sha256" not in body["items"][0]


def test_list_documents_rejects_excessive_limit() -> None:
    client = _client(FakeDocumentRepository())
    knowledge_base_id = uuid4()

    response = client.get(
        f"/knowledge-bases/{knowledge_base_id}/documents?limit=101"
    )

    assert response.status_code == 422


def test_list_documents_does_not_leak_persistence_errors() -> None:
    repository = FakeDocumentRepository()
    repository.fail = True
    client = _client(repository)

    response = client.get(
        f"/knowledge-bases/{uuid4()}/documents"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "document service temporarily unavailable"
    }
    assert "database details" not in response.text
