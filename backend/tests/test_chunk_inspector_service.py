import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.documents.chunk_inspector import (
    ChunkInspectionItem,
    ChunkInspectionQueryError,
    ChunkInspectorService,
)


class FakeChunkInspectorRepository:
    def __init__(self) -> None:
        self.items: tuple[ChunkInspectionItem, ...] = ()
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
        return self.items[offset : offset + limit]


def test_chunk_inspector_preserves_scope_and_embedding_availability() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    repository = FakeChunkInspectorRepository()
    repository.items = (
        ChunkInspectionItem(
            id=uuid4(),
            document_id=document_id,
            index=0,
            text="first chunk",
            start_offset=0,
            end_offset=11,
            embedding_count=2,
        ),
    )
    service = ChunkInspectorService(repository)

    result = asyncio.run(
        service.list_by_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            limit=50,
            offset=0,
        )
    )

    assert len(result) == 1
    assert result[0].has_embeddings is True
    assert result[0].embedding_count == 2
    assert repository.last_call == {
        "knowledge_base_id": knowledge_base_id,
        "document_id": document_id,
        "limit": 50,
        "offset": 0,
    }


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (101, 0),
        (True, 0),
        (50, -1),
        (50, True),
    ],
)
def test_chunk_inspector_rejects_invalid_pagination(
    limit: int,
    offset: int,
) -> None:
    service = ChunkInspectorService(FakeChunkInspectorRepository())

    with pytest.raises(ChunkInspectionQueryError):
        asyncio.run(
            service.list_by_document(
                knowledge_base_id=uuid4(),
                document_id=uuid4(),
                limit=limit,
                offset=offset,
            )
        )
