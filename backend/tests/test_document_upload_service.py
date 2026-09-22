import asyncio
from collections.abc import AsyncIterable, Sequence
from uuid import UUID, uuid4

import pytest

from spurel.documents.domain import Document
from spurel.documents.ports import DocumentPersistenceError
from spurel.documents.storage import DocumentStorageError
from spurel.documents.upload_service import (
    DocumentUploadCleanupError,
    DocumentUploadService,
    DocumentUploadSizeMismatchError,
)


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.items: list[Document] = []
        self.fail = False

    async def add(self, document: Document) -> None:
        if self.fail:
            raise DocumentPersistenceError("database unavailable")
        self.items.append(document)

    async def list_by_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[Document]:
        return ()


class FakeBlobStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_delete = False

    async def put(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
    ) -> None:
        data = bytearray()
        async for chunk in chunks:
            data.extend(chunk)
        self.objects[object_key] = bytes(data)

    async def delete(self, *, object_key: str) -> None:
        if self.fail_delete:
            raise DocumentStorageError("provider delete failed")
        self.objects.pop(object_key, None)
        self.deleted.append(object_key)


async def _chunks(*values: bytes) -> AsyncIterable[bytes]:
    for value in values:
        yield value


def test_upload_streams_content_and_registers_metadata() -> None:
    repository = FakeDocumentRepository()
    storage = FakeBlobStorage()
    service = DocumentUploadService(repository=repository, storage=storage)
    knowledge_base_id = uuid4()

    result = asyncio.run(
        service.upload(
            knowledge_base_id=knowledge_base_id,
            filename="architecture.md",
            media_type="text/markdown",
            declared_size_bytes=11,
            chunks=_chunks(b"hello ", b"world"),
        )
    )

    assert repository.items == [result.document]
    assert storage.objects[result.object_key] == b"hello world"
    assert result.object_key.startswith(
        f"knowledge-bases/{knowledge_base_id}/documents/"
    )
    assert "architecture.md" not in result.object_key
    assert result.sha256 == (
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


def test_upload_deletes_blob_when_actual_size_does_not_match() -> None:
    storage = FakeBlobStorage()
    service = DocumentUploadService(
        repository=FakeDocumentRepository(),
        storage=storage,
    )

    with pytest.raises(DocumentUploadSizeMismatchError):
        asyncio.run(
            service.upload(
                knowledge_base_id=uuid4(),
                filename="notes.txt",
                media_type="text/plain",
                declared_size_bytes=10,
                chunks=_chunks(b"short"),
            )
        )

    assert storage.objects == {}
    assert len(storage.deleted) == 1


def test_upload_deletes_blob_when_metadata_persistence_fails() -> None:
    repository = FakeDocumentRepository()
    repository.fail = True
    storage = FakeBlobStorage()
    service = DocumentUploadService(repository=repository, storage=storage)

    with pytest.raises(DocumentPersistenceError):
        asyncio.run(
            service.upload(
                knowledge_base_id=uuid4(),
                filename="notes.txt",
                media_type="text/plain",
                declared_size_bytes=5,
                chunks=_chunks(b"hello"),
            )
        )

    assert storage.objects == {}
    assert len(storage.deleted) == 1


def test_upload_surfaces_cleanup_failure_explicitly() -> None:
    repository = FakeDocumentRepository()
    repository.fail = True
    storage = FakeBlobStorage()
    storage.fail_delete = True
    service = DocumentUploadService(repository=repository, storage=storage)

    with pytest.raises(DocumentUploadCleanupError):
        asyncio.run(
            service.upload(
                knowledge_base_id=uuid4(),
                filename="notes.txt",
                media_type="text/plain",
                declared_size_bytes=5,
                chunks=_chunks(b"hello"),
            )
        )


def test_upload_rejects_stream_larger_than_declared_maximum() -> None:
    storage = FakeBlobStorage()
    service = DocumentUploadService(
        repository=FakeDocumentRepository(),
        storage=storage,
    )

    with pytest.raises(DocumentUploadSizeMismatchError):
        asyncio.run(
            service.upload(
                knowledge_base_id=uuid4(),
                filename="notes.txt",
                media_type="text/plain",
                declared_size_bytes=1,
                chunks=_chunks(b"x" * ((25 * 1024 * 1024) + 1)),
            )
        )

    assert storage.objects == {}
