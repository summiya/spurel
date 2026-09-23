from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.documents.ingestion_service import DocumentNotFoundError
from spurel.documents.parsing import DocumentTextContentError
from spurel.documents.processing import DocumentProcessingResult
from spurel.documents.processing_dependencies import (
    get_document_processing_service,
)
from spurel.embeddings.domain import EmbeddingProviderError
from spurel.main import create_app


class FakeDocumentProcessingService:
    def __init__(self) -> None:
        self.result: DocumentProcessingResult | None = None
        self.error: Exception | None = None
        self.last_call: tuple[UUID, UUID] | None = None

    async def process(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> DocumentProcessingResult:
        self.last_call = (knowledge_base_id, document_id)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _client(service: FakeDocumentProcessingService) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_document_processing_service] = (
        lambda: service
    )
    return TestClient(application)


def test_process_document_returns_complete_pipeline_summary() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    service = FakeDocumentProcessingService()
    service.result = DocumentProcessingResult(
        document_id=document_id,
        knowledge_base_id=knowledge_base_id,
        chunk_count=7,
        embedded_chunk_count=7,
        embedding_provider="openai",
        embedding_model="text-embedding-example",
        embedding_dimensions=1536,
    )
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/process"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "processed",
        "document_id": str(document_id),
        "knowledge_base_id": str(knowledge_base_id),
        "chunk_count": 7,
        "embedded_chunk_count": 7,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-example",
        "embedding_dimensions": 1536,
    }
    assert service.last_call == (knowledge_base_id, document_id)


def test_process_document_returns_not_found_for_scoped_missing_document() -> None:
    service = FakeDocumentProcessingService()
    service.error = DocumentNotFoundError("internal lookup detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "document was not found"}
    assert "internal lookup detail" not in response.text


def test_process_document_hides_provider_failures() -> None:
    service = FakeDocumentProcessingService()
    service.error = EmbeddingProviderError("secret provider detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "document processing service temporarily unavailable"
    }
    assert "secret provider detail" not in response.text


def test_process_document_returns_unprocessable_for_invalid_content() -> None:
    service = FakeDocumentProcessingService()
    service.error = DocumentTextContentError("raw parser detail")
    client = _client(service)

    response = client.post(
        f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process"
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "document cannot be processed"}
    assert "raw parser detail" not in response.text
