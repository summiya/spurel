"""HTTP tests for read-only, scoped chunk-version history."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.documents.chunk_inspector import ChunkInspectionItem
from spurel.documents.dependencies import get_document_version_service
from spurel.documents.versions import (
    DocumentChunkVersion,
    DocumentVersionNotFoundError,
    DocumentVersionPersistenceError,
)
from spurel.main import create_app
from spurel.security import require_api_token


class FakeVersionService:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.calls: list[dict[str, object]] = []
        self.chunk_id = uuid4()

    async def list_versions(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[DocumentChunkVersion, ...]:
        self.calls.append(
            {
                "mode": "versions",
                "knowledge_base_id": knowledge_base_id,
                "document_id": document_id,
                "limit": limit,
                "offset": offset,
            }
        )
        if self.error is not None:
            raise self.error
        return (
            DocumentChunkVersion(
                version=1,
                chunk_count=1,
                created_at=datetime.now(UTC),
                is_active=True,
            ),
        )

    async def list_version_chunks(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        version: int,
        limit: int,
        offset: int,
    ) -> tuple[ChunkInspectionItem, ...]:
        self.calls.append(
            {
                "mode": "chunks",
                "knowledge_base_id": knowledge_base_id,
                "document_id": document_id,
                "version": version,
                "limit": limit,
                "offset": offset,
            }
        )
        if self.error is not None:
            raise self.error
        return (
            ChunkInspectionItem(
                id=self.chunk_id,
                document_id=document_id,
                index=0,
                text="historic refund policy",
                start_offset=0,
                end_offset=22,
                embedding_count=1,
            ),
        )


def _client(service: FakeVersionService) -> TestClient:
    app = create_app()
    app.dependency_overrides[require_api_token] = lambda: None
    app.dependency_overrides[get_document_version_service] = lambda: service
    return TestClient(app)


def test_version_history_and_chunk_inspection_use_scoped_ids() -> None:
    service = FakeVersionService()
    client = _client(service)
    knowledge_base_id = uuid4()
    document_id = uuid4()
    base = f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}"

    versions = client.get(f"{base}/versions?limit=10&offset=0")
    assert versions.status_code == 200
    assert versions.json()["items"][0]["version"] == 1
    assert versions.json()["items"][0]["chunk_count"] == 1
    assert versions.json()["items"][0]["is_active"] is True
    assert versions.json()["items"][0]["status"] == "ready"
    assert versions.json()["items"][0]["attempt_count"] == 0

    history = client.get(f"{base}/versions/1/chunks?limit=10&offset=0")
    assert history.status_code == 200
    assert history.json()["version"] == 1
    assert history.json()["items"][0]["id"] == str(service.chunk_id)
    assert history.json()["items"][0]["has_embeddings"] is True
    assert service.calls[0]["knowledge_base_id"] == knowledge_base_id
    assert service.calls[1]["document_id"] == document_id
    assert service.calls[1]["version"] == 1


def test_version_history_rejects_invalid_page_and_version() -> None:
    client = _client(FakeVersionService())
    base = f"/knowledge-bases/{uuid4()}/documents/{uuid4()}"

    assert client.get(f"{base}/versions?limit=101").status_code == 422
    assert client.get(f"{base}/versions/0/chunks").status_code == 422
    assert client.get(f"{base}/versions/1/chunks?offset=-1").status_code == 422


def test_missing_and_failed_versions_hide_internal_errors() -> None:
    service = FakeVersionService()
    client = _client(service)
    base = f"/knowledge-bases/{uuid4()}/documents/{uuid4()}"

    service.error = DocumentVersionNotFoundError("private document ID")
    assert client.get(f"{base}/versions").status_code == 404
    assert client.get(f"{base}/versions/9/chunks").status_code == 404

    service.error = DocumentVersionPersistenceError("private database details")
    result = client.get(f"{base}/versions")
    assert result.status_code == 503
    assert "private" not in result.text
