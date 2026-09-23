from collections.abc import Sequence
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.documents.chunk_inspector import (
    ChunkInspectionItem,
    ChunkInspectionPersistenceError,
)
from spurel.documents.dependencies import get_chunk_inspector_service
from spurel.main import create_app


class FakeChunkInspectorService:
    def __init__(self) -> None:
        self.items: Sequence[ChunkInspectionItem] = ()
        self.fail = False
        self.last_call: dict[str, object] | None = None

    async def list_by_document(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkInspectionItem]:
        self.last_call = {
            "knowledge_base_id": knowledge_base_id,
            "document_id": document_id,
            "limit": limit,
            "offset": offset,
        }
        if self.fail:
            raise ChunkInspectionPersistenceError("database secret details")
        return self.items


def _client(service: FakeChunkInspectorService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_chunk_inspector_service] = lambda: service
    return TestClient(application)


def test_chunk_inspector_returns_safe_persisted_chunk_data() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    service = FakeChunkInspectorService()
    service.items = (
        ChunkInspectionItem(
            id=uuid4(),
            document_id=document_id,
            index=0,
            text="persisted chunk text",
            start_offset=10,
            end_offset=30,
            embedding_count=2,
        ),
        ChunkInspectionItem(
            id=uuid4(),
            document_id=document_id,
            index=1,
            text="not embedded yet",
            start_offset=30,
            end_offset=46,
            embedding_count=0,
        ),
    )
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/chunks",
        params={"limit": 25, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert body["items"][0]["index"] == 0
    assert body["items"][0]["has_embeddings"] is True
    assert body["items"][0]["embedding_count"] == 2
    assert body["items"][1]["has_embeddings"] is False
    assert body["items"][1]["embedding_count"] == 0
    assert service.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "document_id": document_id,
        "limit": 25,
        "offset": 0,
    }


def test_chunk_inspector_bounds_page_size() -> None:
    client = _client(FakeChunkInspectorService())

    response = client.get(
        f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/chunks",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_chunk_inspector_hides_persistence_errors() -> None:
    service = FakeChunkInspectorService()
    service.fail = True
    client = _client(service)

    response = client.get(
        f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/chunks"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "chunk inspector temporarily unavailable"
    }
    assert "secret details" not in response.text
