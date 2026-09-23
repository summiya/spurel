import hashlib
from collections.abc import AsyncIterable
from uuid import UUID

from fastapi.testclient import TestClient

from spurel.documents.dependencies import get_document_upload_service
from spurel.documents.domain import Document
from spurel.documents.upload_service import DocumentUploadError, DocumentUploadResult
from spurel.main import create_app


class FakeDocumentUploadService:
    def __init__(self) -> None:
        self.fail = False
        self.received_content: bytes | None = None

    async def upload(
        self,
        *,
        knowledge_base_id: UUID,
        filename: str,
        media_type: str,
        declared_size_bytes: int,
        chunks: AsyncIterable[bytes],
    ) -> DocumentUploadResult:
        if self.fail:
            raise DocumentUploadError("provider path /private/storage leaked")

        data = bytearray()
        async for chunk in chunks:
            data.extend(chunk)

        self.received_content = bytes(data)
        document = Document.create(
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            media_type=media_type,
            size_bytes=declared_size_bytes,
        )
        return DocumentUploadResult(
            document=document,
            object_key="internal/storage/key",
            sha256=hashlib.sha256(self.received_content).hexdigest(),
        )


def _client(service: FakeDocumentUploadService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_document_upload_service] = lambda: service
    return TestClient(application)


def test_upload_document_streams_file_and_hides_storage_key() -> None:
    service = FakeDocumentUploadService()
    client = _client(service)

    response = client.post(
        "/knowledge-bases/11111111-1111-1111-1111-111111111111/documents",
        files={"file": ("architecture.md", b"hello world", "text/markdown")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "architecture.md"
    assert body["media_type"] == "text/markdown"
    assert body["size_bytes"] == 11
    assert body["sha256"] == (
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )
    assert "object_key" not in body
    assert "internal/storage/key" not in response.text
    assert service.received_content == b"hello world"


def test_upload_document_rejects_unsupported_media_type() -> None:
    service = FakeDocumentUploadService()
    client = _client(service)

    response = client.post(
        "/knowledge-bases/11111111-1111-1111-1111-111111111111/documents",
        files={"file": ("archive.zip", b"data", "application/zip")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "document upload is invalid"}


def test_upload_document_does_not_leak_internal_failure_details() -> None:
    service = FakeDocumentUploadService()
    service.fail = True
    client = _client(service)

    response = client.post(
        "/knowledge-bases/11111111-1111-1111-1111-111111111111/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "document upload service temporarily unavailable"
    }
    assert "/private/storage" not in response.text
