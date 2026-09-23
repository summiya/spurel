import asyncio
from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

import pytest

from spurel.documents.chunk_pipeline import DocumentChunkPipeline
from spurel.documents.chunk_service import DocumentChunkService
from spurel.documents.chunking import DocumentChunk, DocumentChunker
from spurel.documents.domain import Document, DocumentMediaType
from spurel.documents.ingestion_service import DocumentIngestionService
from spurel.documents.parsing import DocumentParser, ParsedDocument
from spurel.documents.ports import DocumentRepository
from spurel.documents.storage import DocumentBlobStorage, document_object_key


class FakeDocumentRepository(DocumentRepository):
    def __init__(self, document: Document) -> None:
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
            self.document.knowledge_base_id == knowledge_base_id
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


class FakeBlobStorage(DocumentBlobStorage):
    def __init__(self, *, object_key: str, content: bytes) -> None:
        self.object_key = object_key
        self.content = content

    async def put(self, *, object_key: str, chunks) -> None:
        raise NotImplementedError

    async def get(self, *, object_key: str) -> bytes:
        assert object_key == self.object_key
        return self.content

    async def delete(self, *, object_key: str) -> None:
        raise NotImplementedError


class FakeParser(DocumentParser):
    def parse(
        self,
        *,
        content: bytes,
        media_type: DocumentMediaType,
    ) -> ParsedDocument:
        return ParsedDocument(
            text=content.decode("utf-8"),
            media_type=media_type,
        )


class FakeChunkRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, tuple[DocumentChunk, ...]] = {}

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        chunks: Sequence[DocumentChunk],
    ) -> None:
        self.items[document_id] = tuple(chunks)

    async def list_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[DocumentChunk]:
        return self.items.get(document_id, ())[offset : offset + limit]


class TwoChunkChunker(DocumentChunker):
    def chunk(self, *, text: str) -> Sequence[DocumentChunk]:
        midpoint = len(text) // 2
        return (
            DocumentChunk(
                index=0,
                text=text[:midpoint],
                start_offset=0,
                end_offset=midpoint,
            ),
            DocumentChunk(
                index=1,
                text=text[midpoint:],
                start_offset=midpoint,
                end_offset=len(text),
            ),
        )


def _build_pipeline(
    *,
    document: Document,
    content: bytes,
    chunk_repository: FakeChunkRepository,
    chunker: DocumentChunker,
) -> DocumentChunkPipeline:
    parsers: Mapping[DocumentMediaType, DocumentParser] = {
        DocumentMediaType.TEXT: FakeParser()
    }
    ingestion_service = DocumentIngestionService(
        repository=FakeDocumentRepository(document),
        storage=FakeBlobStorage(
            object_key=document_object_key(document),
            content=content,
        ),
        parsers=parsers,
    )
    chunk_service = DocumentChunkService(chunk_repository)

    return DocumentChunkPipeline(
        ingestion_service=ingestion_service,
        chunker=chunker,
        chunk_service=chunk_service,
    )


def test_pipeline_parses_chunks_and_persists_document_chunks() -> None:
    content = b"abcdefgh"
    document = Document.create(
        knowledge_base_id=uuid4(),
        filename="notes.txt",
        media_type="text/plain",
        size_bytes=len(content),
    )
    chunk_repository = FakeChunkRepository()
    pipeline = _build_pipeline(
        document=document,
        content=content,
        chunk_repository=chunk_repository,
        chunker=TwoChunkChunker(),
    )

    result = asyncio.run(
        pipeline.run(
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
        )
    )

    assert result.document_id == document.id
    assert result.knowledge_base_id == document.knowledge_base_id
    assert result.chunk_count == 2
    assert [chunk.text for chunk in chunk_repository.items[document.id]] == [
        "abcd",
        "efgh",
    ]


def test_pipeline_reprocessing_replaces_previous_chunk_set() -> None:
    first_content = b"abcdefgh"
    document = Document.create(
        knowledge_base_id=uuid4(),
        filename="notes.txt",
        media_type="text/plain",
        size_bytes=len(first_content),
    )
    chunk_repository = FakeChunkRepository()

    first_pipeline = _build_pipeline(
        document=document,
        content=first_content,
        chunk_repository=chunk_repository,
        chunker=TwoChunkChunker(),
    )
    asyncio.run(
        first_pipeline.run(
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
        )
    )

    replacement = (
        DocumentChunk(
            index=0,
            text="replacement",
            start_offset=0,
            end_offset=11,
        ),
    )

    class ReplacementChunker(DocumentChunker):
        def chunk(self, *, text: str) -> Sequence[DocumentChunk]:
            return replacement

    second_pipeline = _build_pipeline(
        document=document,
        content=first_content,
        chunk_repository=chunk_repository,
        chunker=ReplacementChunker(),
    )
    asyncio.run(
        second_pipeline.run(
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
        )
    )

    assert chunk_repository.items[document.id] == replacement


def test_pipeline_does_not_persist_when_chunking_fails() -> None:
    content = b"abcdefgh"
    document = Document.create(
        knowledge_base_id=uuid4(),
        filename="notes.txt",
        media_type="text/plain",
        size_bytes=len(content),
    )
    chunk_repository = FakeChunkRepository()

    class FailingChunker(DocumentChunker):
        def chunk(self, *, text: str) -> Sequence[DocumentChunk]:
            raise ValueError("chunking failed")

    pipeline = _build_pipeline(
        document=document,
        content=content,
        chunk_repository=chunk_repository,
        chunker=FailingChunker(),
    )

    with pytest.raises(ValueError, match="chunking failed"):
        asyncio.run(
            pipeline.run(
                knowledge_base_id=document.knowledge_base_id,
                document_id=document.id,
            )
        )

    assert document.id not in chunk_repository.items
