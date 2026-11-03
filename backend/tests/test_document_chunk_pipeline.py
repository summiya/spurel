import asyncio
from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

import pytest

from spurel.documents.chunk_models import StagedDocumentChunkSet
from spurel.documents.chunk_pipeline import DocumentChunkPipeline, _apply_pdf_page_spans
from spurel.documents.chunk_service import DocumentChunkService
from spurel.documents.chunking import DocumentChunk, DocumentChunker
from spurel.documents.domain import Document, DocumentMediaType
from spurel.documents.ingestion_service import DocumentIngestionService
from spurel.documents.parsing import DocumentParser, ParsedDocument, ParsedPageSpan
from spurel.documents.ports import DocumentRepository
from spurel.documents.storage import DocumentBlobStorage, document_object_key
from spurel.infrastructure.chunking.fixed import FixedSizeDocumentChunker


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
        if self.document.knowledge_base_id == knowledge_base_id and self.document.id == document_id:
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
    ) -> StagedDocumentChunkSet:
        self.items[document_id] = tuple(chunks)
        return StagedDocumentChunkSet(version=1, attempt_id=None, reused_active=True)

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
    parsers: Mapping[DocumentMediaType, DocumentParser] = {DocumentMediaType.TEXT: FakeParser()}
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


def test_pipeline_can_opt_in_to_new_chunker_without_replacing_default() -> None:
    content = b"abcdefghijklmnop"
    document = Document.create(
        knowledge_base_id=uuid4(),
        filename="notes.txt",
        media_type="text/plain",
        size_bytes=len(content),
    )
    repository = FakeChunkRepository()
    pipeline = _build_pipeline(
        document=document,
        content=content,
        chunk_repository=repository,
        chunker=FixedSizeDocumentChunker(chunk_size=8, overlap=2),
    )
    asyncio.run(
        pipeline.run(
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            chunker=FixedSizeDocumentChunker(chunk_size=5, overlap=0),
        )
    )
    assert repository.items[document.id][0].text == "abcde"

    # The configured default chunker was not mutated by the opt-in run.
    asyncio.run(pipeline.run(knowledge_base_id=document.knowledge_base_id, document_id=document.id))
    assert repository.items[document.id][0].text == "abcdefgh"



def test_pdf_page_spans_annotate_chunks_without_changing_offsets_or_text() -> None:
    source = "Page one.\n\nPage two."
    page_two = source.index("Page two")
    parts = (
        DocumentChunk(index=0, text=source[:page_two], start_offset=0, end_offset=page_two),
        DocumentChunk(
            index=1, text=source[page_two:], start_offset=page_two, end_offset=len(source)
        ),
    )
    pages = (
        ParsedPageSpan(page_number=1, start_offset=0, end_offset=9),
        ParsedPageSpan(
            page_number=2, start_offset=page_two, end_offset=len(source), used_ocr=True
        ),
    )
    result = _apply_pdf_page_spans(parts, pages)
    assert result[0].page_start == 1
    assert result[0].page_end == 1
    assert not result[0].ocr_used
    assert result[1].page_start == 2
    assert result[1].page_end == 2
    assert result[1].ocr_used
    assert [(chunk.text, chunk.start_offset, chunk.end_offset) for chunk in result] == [
        (part.text, part.start_offset, part.end_offset) for part in parts
    ]


def test_pdf_chunks_spanning_two_pages_have_a_real_page_range() -> None:
    parts = (DocumentChunk(index=0, text="AA\n\nBB", start_offset=0, end_offset=6),)
    pages = (
        ParsedPageSpan(page_number=1, start_offset=0, end_offset=2),
        ParsedPageSpan(page_number=3, start_offset=4, end_offset=6, used_ocr=True),
    )
    [result] = _apply_pdf_page_spans(parts, pages)
    assert (result.page_start, result.page_end, result.ocr_used) == (1, 3, True)


def test_non_pdf_chunk_pipeline_stays_identical_without_page_metadata() -> None:
    chunks = (
        DocumentChunk(index=0, text="Plain text", start_offset=0, end_offset=10),
    )
    assert _apply_pdf_page_spans(chunks, ()) == chunks
