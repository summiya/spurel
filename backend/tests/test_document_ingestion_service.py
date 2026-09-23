import asyncio
from collections.abc import AsyncIterable, Sequence
from uuid import UUID, uuid4

import pytest

from spurel.documents.domain import Document, DocumentMediaType
from spurel.documents.ingestion_service import (
    DocumentContentSizeMismatchError,
    DocumentContentUnavailableError,
    DocumentIngestionService,
    DocumentNotFoundError,
)
from spurel.documents.parsing import ParsedDocument
from spurel.documents.storage import DocumentStorageError, document_object_key


class FakeDocumentRepository:
    def __init__(self, document: Document | None) -> None:
        self.document = document

    async def add(self, document: Document) -> None:
        self.document = document

    async def get_by_id(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> Document | None:
        if (
            self.document is not None
            and self.document.knowledge_base_id == knowledge_base_id
            and self.document.id == document_id
        ):
            return self.document
        return None

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        return ()


class FakeBlobStorage:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.fail = False
        self.last_key: str | None = None

    async def put(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
    ) -> None:
        raise NotImplementedError

    async def get(self, *, object_key: str) -> bytes:
        self.last_key = object_key
        if self.fail:
            raise DocumentStorageError("provider details")
        return self.content

    async def delete(self, *, object_key: str) -> None:
        raise NotImplementedError


class FakeParser:
    def __init__(self) -> None:
        self.received: bytes | None = None

    def parse(
        self,
        *,
        content: bytes,
        media_type: DocumentMediaType,
    ) -> ParsedDocument:
        self.received = content
        return ParsedDocument(
            text=content.decode("utf-8"),
            media_type=media_type,
        )


def _document(*, content: bytes) -> Document:
    return Document.create(
        knowledge_base_id=uuid4(),
        filename="notes.txt",
        media_type="text/plain",
        size_bytes=len(content),
    )


def test_ingest_loads_scoped_blob_and_selects_parser() -> None:
    content = b"hello world"
    document = _document(content=content)
    storage = FakeBlobStorage(content)
    parser = FakeParser()
    service = DocumentIngestionService(
        repository=FakeDocumentRepository(document),
        storage=storage,
        parsers={DocumentMediaType.TEXT: parser},
    )

    result = asyncio.run(
        service.ingest(
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
        )
    )

    assert result.document_id == document.id
    assert result.knowledge_base_id == document.knowledge_base_id
    assert result.parsed.text == "hello world"
    assert parser.received == content
    assert storage.last_key == document_object_key(document)


def test_ingest_rejects_document_outside_requested_knowledge_base() -> None:
    content = b"hello"
    document = _document(content=content)
    service = DocumentIngestionService(
        repository=FakeDocumentRepository(document),
        storage=FakeBlobStorage(content),
        parsers={DocumentMediaType.TEXT: FakeParser()},
    )

    with pytest.raises(DocumentNotFoundError):
        asyncio.run(
            service.ingest(
                knowledge_base_id=uuid4(),
                document_id=document.id,
            )
        )


def test_ingest_rejects_stored_size_mismatch() -> None:
    document = _document(content=b"hello")
    service = DocumentIngestionService(
        repository=FakeDocumentRepository(document),
        storage=FakeBlobStorage(b"truncated"),
        parsers={DocumentMediaType.TEXT: FakeParser()},
    )

    with pytest.raises(DocumentContentSizeMismatchError):
        asyncio.run(
            service.ingest(
                knowledge_base_id=document.knowledge_base_id,
                document_id=document.id,
            )
        )


def test_ingest_hides_storage_failure_details() -> None:
    content = b"hello"
    document = _document(content=content)
    storage = FakeBlobStorage(content)
    storage.fail = True
    service = DocumentIngestionService(
        repository=FakeDocumentRepository(document),
        storage=storage,
        parsers={DocumentMediaType.TEXT: FakeParser()},
    )

    with pytest.raises(DocumentContentUnavailableError) as exc_info:
        asyncio.run(
            service.ingest(
                knowledge_base_id=document.knowledge_base_id,
                document_id=document.id,
            )
        )

    assert "provider details" not in str(exc_info.value)
