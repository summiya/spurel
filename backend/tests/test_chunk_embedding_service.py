import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.domain import EmbeddingVector
from spurel.embeddings.service import (
    ChunkEmbeddingBatchError,
    ChunkEmbeddingService,
)


class FakeChunkEmbeddingRepository:
    def __init__(self) -> None:
        self.items: dict[
            tuple[UUID, str, str, int],
            ChunkEmbedding,
        ] = {}

    async def upsert_batch(
        self,
        embeddings: Sequence[ChunkEmbedding],
    ) -> None:
        for embedding in embeddings:
            key = (
                embedding.chunk_id,
                embedding.provider,
                embedding.model,
                embedding.dimensions,
            )
            self.items[key] = embedding

    async def list_by_chunk(
        self,
        *,
        chunk_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[ChunkEmbedding]:
        matches = sorted(
            (
                embedding
                for embedding in self.items.values()
                if embedding.chunk_id == chunk_id
            ),
            key=lambda embedding: (
                embedding.provider,
                embedding.model,
                embedding.dimensions,
            ),
        )
        return tuple(matches[offset : offset + limit])


def _embedding(
    *,
    chunk_id: UUID,
    provider: str = "openai",
    model: str = "text-embedding-example",
    dimensions: int = 2,
    values: tuple[float, ...] = (0.1, 0.2),
) -> ChunkEmbedding:
    return ChunkEmbedding.create(
        chunk_id=chunk_id,
        provider=provider,
        model=model,
        vector=EmbeddingVector.create(
            values,
            expected_dimensions=dimensions,
        ),
    )


def test_upsert_batch_persists_one_embedding_space() -> None:
    repository = FakeChunkEmbeddingRepository()
    service = ChunkEmbeddingService(repository)
    first_chunk_id = uuid4()
    second_chunk_id = uuid4()
    embeddings = (
        _embedding(chunk_id=first_chunk_id),
        _embedding(chunk_id=second_chunk_id),
    )

    asyncio.run(service.upsert_batch(embeddings))

    assert len(repository.items) == 2


def test_upsert_batch_replaces_same_chunk_embedding_space() -> None:
    repository = FakeChunkEmbeddingRepository()
    service = ChunkEmbeddingService(repository)
    chunk_id = uuid4()

    asyncio.run(
        service.upsert_batch(
            (_embedding(chunk_id=chunk_id),)
        )
    )
    replacement = _embedding(
        chunk_id=chunk_id,
        values=(0.9, 0.8),
    )
    asyncio.run(service.upsert_batch((replacement,)))

    assert len(repository.items) == 1
    assert next(iter(repository.items.values())).vector.values == (0.9, 0.8)


def test_upsert_batch_preserves_other_embedding_spaces() -> None:
    repository = FakeChunkEmbeddingRepository()
    service = ChunkEmbeddingService(repository)
    chunk_id = uuid4()

    first = _embedding(chunk_id=chunk_id)
    second = _embedding(
        chunk_id=chunk_id,
        provider="local",
        model="another-model",
    )

    asyncio.run(service.upsert_batch((first,)))
    asyncio.run(service.upsert_batch((second,)))

    assert len(repository.items) == 2


def test_upsert_batch_rejects_mixed_embedding_spaces() -> None:
    service = ChunkEmbeddingService(FakeChunkEmbeddingRepository())

    with pytest.raises(ChunkEmbeddingBatchError):
        asyncio.run(
            service.upsert_batch(
                (
                    _embedding(chunk_id=uuid4()),
                    _embedding(
                        chunk_id=uuid4(),
                        provider="local",
                    ),
                )
            )
        )


def test_upsert_batch_rejects_duplicate_chunk_ids() -> None:
    service = ChunkEmbeddingService(FakeChunkEmbeddingRepository())
    chunk_id = uuid4()

    with pytest.raises(ChunkEmbeddingBatchError):
        asyncio.run(
            service.upsert_batch(
                (
                    _embedding(chunk_id=chunk_id),
                    _embedding(chunk_id=chunk_id),
                )
            )
        )


def test_list_by_chunk_is_bounded() -> None:
    repository = FakeChunkEmbeddingRepository()
    service = ChunkEmbeddingService(repository)
    chunk_id = uuid4()

    asyncio.run(
        repository.upsert_batch(
            (
                _embedding(chunk_id=chunk_id),
                _embedding(
                    chunk_id=chunk_id,
                    provider="local",
                    model="another-model",
                ),
            )
        )
    )

    result = asyncio.run(
        service.list_by_chunk(
            chunk_id=chunk_id,
            limit=1,
            offset=1,
        )
    )

    assert len(result) == 1
