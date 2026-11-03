from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from spurel.documents.chunk_options import ChunkStrategy, DocumentChunkOptions
from spurel.documents.ingestion_service import DocumentNotFoundError
from spurel.documents.parsing import DocumentTextContentError
from spurel.documents.processing import DocumentProcessingResult
from spurel.documents.processing_dependencies import (
    get_document_processing_service,
)
from spurel.embeddings.domain import EmbeddingProviderError
from spurel.main import create_app
from spurel.security import require_api_token


class FakeDocumentProcessingService:
    def __init__(self) -> None:
        self.result: DocumentProcessingResult | None = None
        self.error: Exception | None = None
        self.last_call: tuple[UUID, UUID] | None = None
        self.last_options: DocumentChunkOptions | None = None

    async def process(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
        chunk_options: DocumentChunkOptions | None = None,
    ) -> DocumentProcessingResult:
        self.last_call = (knowledge_base_id, document_id)
        self.last_options = chunk_options
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _client(service: FakeDocumentProcessingService) -> TestClient:
    application = create_app()
    application.dependency_overrides[require_api_token] = lambda: None
    application.dependency_overrides[get_document_processing_service] = lambda: service
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

    response = client.post(f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/process")

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
        "chunk_version": 1,
        "reused_active_version": False,
    }
    assert service.last_call == (knowledge_base_id, document_id)


def test_process_document_returns_not_found_for_scoped_missing_document() -> None:
    service = FakeDocumentProcessingService()
    service.error = DocumentNotFoundError("internal lookup detail")
    client = _client(service)

    response = client.post(f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process")

    assert response.status_code == 404
    assert response.json() == {"detail": "document was not found"}
    assert "internal lookup detail" not in response.text


def test_process_document_hides_provider_failures() -> None:
    service = FakeDocumentProcessingService()
    service.error = EmbeddingProviderError("secret provider detail")
    client = _client(service)

    response = client.post(f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process")

    assert response.status_code == 503
    assert response.json() == {"detail": "document processing service temporarily unavailable"}
    assert "secret provider detail" not in response.text


def test_process_document_returns_unprocessable_for_invalid_content() -> None:
    service = FakeDocumentProcessingService()
    service.error = DocumentTextContentError("raw parser detail")
    client = _client(service)

    response = client.post(f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process")

    assert response.status_code == 422
    assert response.json() == {"detail": "document cannot be processed"}
    assert "raw parser detail" not in response.text


def test_process_document_accepts_explicit_token_chunking_without_changing_legacy_post() -> None:
    kb_id = uuid4()
    doc_id = uuid4()
    service = FakeDocumentProcessingService()
    service.result = DocumentProcessingResult(
        document_id=doc_id,
        knowledge_base_id=kb_id,
        chunk_count=2,
        embedded_chunk_count=2,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
    )
    client = _client(service)
    endpoint = f"/knowledge-bases/{kb_id}/documents/{doc_id}/process"

    response = client.post(endpoint, json={"strategy": "tokens", "chunk_size": 512, "overlap": 64})
    assert response.status_code == 200
    assert service.last_options == DocumentChunkOptions(
        strategy=ChunkStrategy.TOKENS, chunk_size=512, overlap=64
    )

    response = client.post(endpoint)
    assert response.status_code == 200
    assert service.last_options is None


def test_processing_rejects_unsafe_token_settings_before_running_pipeline() -> None:
    service = FakeDocumentProcessingService()
    client = _client(service)
    endpoint = f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process"
    invalid = [
        {"strategy": "tokens", "chunk_size": 2001, "overlap": 10},
        {"strategy": "tokens", "chunk_size": 512, "overlap": 512},
        {"strategy": "unknown", "chunk_size": 100, "overlap": 10},
        {"strategy": "characters", "chunk_size": 20001, "overlap": 100},
        {"strategy": "tokens", "chunk_size": True, "overlap": 0},
        {"strategy": "tokens", "chunk_size": 512, "overlap": 32, "extra": "not allowed"},
    ]
    for body in invalid:
        assert client.post(endpoint, json=body).status_code == 422
    assert service.last_call is None


def test_sp17_structured_strategies_are_explicit_and_do_not_change_legacy_requests() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    service = FakeDocumentProcessingService()
    service.result = DocumentProcessingResult(
        document_id=document_id,
        knowledge_base_id=knowledge_base_id,
        chunk_count=2,
        embedded_chunk_count=2,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
    )
    client = _client(service)
    endpoint = f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/process"

    for strategy in ("recursive", "markdown", "sentences"):
        response = client.post(
            endpoint, json={"strategy": strategy, "chunk_size": 512, "overlap": 64}
        )
        assert response.status_code == 200
        assert service.last_options == DocumentChunkOptions(
            strategy=ChunkStrategy(strategy), chunk_size=512, overlap=64
        )

    response = client.post(endpoint)
    assert response.status_code == 200
    assert service.last_options is None


def test_sp17_rejects_malformed_structured_settings_before_processing() -> None:
    service = FakeDocumentProcessingService()
    client = _client(service)
    endpoint = f"/knowledge-bases/{uuid4()}/documents/{uuid4()}/process"

    for payload in (
        {"strategy": "markdown", "chunk_size": 0, "overlap": 0},
        {"strategy": "recursive", "chunk_size": 100, "overlap": 100},
        {"strategy": "sentences", "chunk_size": 20001, "overlap": 10},
        {"strategy": "sentences", "chunk_size": True, "overlap": 0},
        {"strategy": "recursive", "chunk_size": 100, "overlap": 0, "data": "extra"},
        {"strategy": "not-supported", "chunk_size": 100, "overlap": 10},
    ):
        assert client.post(endpoint, json=payload).status_code == 422

    assert service.last_call is None
