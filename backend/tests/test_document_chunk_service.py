import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.documents.chunk_ports import DocumentChunkRepository
from spurel.documents.chunk_service import (
    DocumentChunkService,
    DocumentChunkSetError,
)
from spurel.documents.chunking import DocumentChunk


class FakeDocumentChunkRepository(DocumentChunkRepository):
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
        chunks = self.items.get(document_id, ())
        return chunks[offset : offset + limit]


def _chunks() -> tuple[DocumentChunk, ...]:
    return (
        DocumentChunk(
            index=0,
            text="abcde",
            start_offset=0,
            end_offset=5,
        ),
        DocumentChunk(
            index=1,
            text="defgh",
            start_offset=3,
            end_offset=8,
        ),
    )


def test_replace_document_chunks_through_service() -> None:
    repository = FakeDocumentChunkRepository()
    service = DocumentChunkService(repository)
    document_id = uuid4()

    asyncio.run(
        service.replace_for_document(
            document_id=document_id,
            chunks=_chunks(),
        )
    )

    assert repository.items[document_id] == _chunks()


def test_replace_overwrites_previous_chunk_set() -> None:
    repository = FakeDocumentChunkRepository()
    service = DocumentChunkService(repository)
    document_id = uuid4()

    asyncio.run(
        service.replace_for_document(
            document_id=document_id,
            chunks=_chunks(),
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

    asyncio.run(
        service.replace_for_document(
            document_id=document_id,
            chunks=replacement,
        )
    )

    assert repository.items[document_id] == replacement


@pytest.mark.parametrize(
    "chunks",
    [
        (),
        (
            DocumentChunk(
                index=1,
                text="starts wrong",
                start_offset=0,
                end_offset=12,
            ),
        ),
        (
            DocumentChunk(
                index=0,
                text="first",
                start_offset=0,
                end_offset=5,
            ),
            DocumentChunk(
                index=2,
                text="gap",
                start_offset=5,
                end_offset=8,
            ),
        ),
    ],
)
def test_replace_rejects_invalid_chunk_set(
    chunks: tuple[DocumentChunk, ...],
) -> None:
    service = DocumentChunkService(FakeDocumentChunkRepository())

    with pytest.raises(DocumentChunkSetError):
        asyncio.run(
            service.replace_for_document(
                document_id=uuid4(),
                chunks=chunks,
            )
        )


def test_list_document_chunks_is_bounded() -> None:
    repository = FakeDocumentChunkRepository()
    service = DocumentChunkService(repository)
    document_id = uuid4()
    repository.items[document_id] = _chunks()

    result = asyncio.run(
        service.list_by_document(
            document_id=document_id,
            limit=1,
            offset=1,
        )
    )

    assert tuple(result) == (_chunks()[1],)
