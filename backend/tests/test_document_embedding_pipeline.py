import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from spurel.documents.chunk_models import StoredDocumentChunk
from spurel.documents.chunking import DocumentChunk
from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.domain import EmbeddingBatch
from spurel.embeddings.pipeline import (
    DocumentEmbeddingNoChunksError,
    DocumentEmbeddingPipeline,
    DocumentEmbeddingProviderContractError,
)
from spurel.embeddings.service import ChunkEmbeddingService


class FakeStoredChunkReader:
    def __init__(self, chunks: Sequence[StoredDocumentChunk]) -> None:
        self.chunks = tuple(chunks)

    async def list_stored_by_document(
        self,
        *,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> Sequence[StoredDocumentChunk]:
        matches = [
            stored
            for stored in self.chunks
            if stored.document_id == document_id
        ]
        return tuple(matches[offset : offset + limit])


class FakeEmbeddingProvider:
    provider = "test-provider"
    model = "test-model"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.override_model: str | None = None
        self.override_dimensions: int | None = None

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self.calls.append(tuple(texts))
        dimensions = self.override_dimensions or self.dimensions
        model = self.override_model or self.model

        return EmbeddingBatch.create(
            vectors=[
                [float(index + 1)] * dimensions
                for index, _ in enumerate(texts)
            ],
            input_count=len(texts),
            model=model,
            dimensions=dimensions,
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
        matches = [
            embedding
            for embedding in self.items.values()
            if embedding.chunk_id == chunk_id
        ]
        return tuple(matches[offset : offset + limit])


def _stored_chunks(
    *,
    document_id: UUID,
    count: int,
) -> tuple[StoredDocumentChunk, ...]:
    return tuple(
        StoredDocumentChunk(
            id=uuid4(),
            document_id=document_id,
            chunk=DocumentChunk(
                index=index,
                text=f"chunk-{index}",
                start_offset=index * 10,
                end_offset=(index * 10) + 7,
            ),
        )
        for index in range(count)
    )


def test_pipeline_pages_chunks_through_provider_and_persists_vectors() -> None:
    document_id = uuid4()
    chunks = _stored_chunks(document_id=document_id, count=5)
    provider = FakeEmbeddingProvider()
    repository = FakeChunkEmbeddingRepository()
    pipeline = DocumentEmbeddingPipeline(
        chunk_reader=FakeStoredChunkReader(chunks),
        provider=provider,
        embedding_service=ChunkEmbeddingService(repository),
        batch_size=2,
    )

    result = asyncio.run(pipeline.run(document_id=document_id))

    assert provider.calls == [
        ("chunk-0", "chunk-1"),
        ("chunk-2", "chunk-3"),
        ("chunk-4",),
    ]
    assert result.embedded_chunk_count == 5
    assert result.provider == "test-provider"
    assert result.model == "test-model"
    assert result.dimensions == 2
    assert len(repository.items) == 5
    assert {
        key[0] for key in repository.items
    } == {stored.id for stored in chunks}


def test_pipeline_is_idempotent_for_same_embedding_space() -> None:
    document_id = uuid4()
    chunks = _stored_chunks(document_id=document_id, count=2)
    repository = FakeChunkEmbeddingRepository()
    pipeline = DocumentEmbeddingPipeline(
        chunk_reader=FakeStoredChunkReader(chunks),
        provider=FakeEmbeddingProvider(),
        embedding_service=ChunkEmbeddingService(repository),
    )

    asyncio.run(pipeline.run(document_id=document_id))
    asyncio.run(pipeline.run(document_id=document_id))

    assert len(repository.items) == 2


def test_pipeline_rejects_document_without_chunks() -> None:
    pipeline = DocumentEmbeddingPipeline(
        chunk_reader=FakeStoredChunkReader(()),
        provider=FakeEmbeddingProvider(),
        embedding_service=ChunkEmbeddingService(
            FakeChunkEmbeddingRepository()
        ),
    )

    with pytest.raises(DocumentEmbeddingNoChunksError):
        asyncio.run(pipeline.run(document_id=uuid4()))


def test_pipeline_rejects_provider_model_contract_mismatch() -> None:
    document_id = uuid4()
    chunks = _stored_chunks(document_id=document_id, count=1)
    provider = FakeEmbeddingProvider()
    provider.override_model = "unexpected-model"
    repository = FakeChunkEmbeddingRepository()
    pipeline = DocumentEmbeddingPipeline(
        chunk_reader=FakeStoredChunkReader(chunks),
        provider=provider,
        embedding_service=ChunkEmbeddingService(repository),
    )

    with pytest.raises(DocumentEmbeddingProviderContractError):
        asyncio.run(pipeline.run(document_id=document_id))

    assert repository.items == {}


def test_pipeline_rejects_provider_dimension_contract_mismatch() -> None:
    document_id = uuid4()
    chunks = _stored_chunks(document_id=document_id, count=1)
    provider = FakeEmbeddingProvider()
    provider.override_dimensions = 3
    repository = FakeChunkEmbeddingRepository()
    pipeline = DocumentEmbeddingPipeline(
        chunk_reader=FakeStoredChunkReader(chunks),
        provider=provider,
        embedding_service=ChunkEmbeddingService(repository),
    )

    with pytest.raises(DocumentEmbeddingProviderContractError):
        asyncio.run(pipeline.run(document_id=document_id))

    assert repository.items == {}
