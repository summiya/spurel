import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from spurel.documents.chunk_pipeline import DocumentChunkPipelineResult
from spurel.documents.chunk_options import ChunkStrategy, DocumentChunkOptions
from spurel.infrastructure.chunking.fixed import FixedSizeDocumentChunker
from spurel.documents.processing import DocumentProcessingService
from spurel.embeddings.pipeline import DocumentEmbeddingPipelineResult


@dataclass
class FakeChunkPipeline:
    result: DocumentChunkPipelineResult
    error: Exception | None = None
    calls: list[tuple[UUID, UUID]] | None = None
    events: list[str] | None = None

    def __post_init__(self) -> None:
        self.calls = []
        self.events = []

    async def renew_version(self, *, document_id: UUID, version: int, attempt_id: UUID) -> None:
        assert self.events is not None
        self.events.append("renew")

    async def promote_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        assert self.events is not None
        self.events.append("promote")

    async def fail_version(self, *, document_id: UUID, version: int, attempt_id: UUID) -> None:
        assert self.events is not None
        self.events.append("fail")

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> DocumentChunkPipelineResult:
        assert self.calls is not None
        self.calls.append((knowledge_base_id, document_id))
        if self.error is not None:
            raise self.error
        return self.result


@dataclass
class FakeEmbeddingPipeline:
    result: DocumentEmbeddingPipelineResult
    error: Exception | None = None
    calls: list[tuple[UUID, int | None]] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    async def run(
        self,
        *,
        document_id: UUID,
        chunk_version: int | None = None,
        before_batch: Callable[[], Awaitable[None]] | None = None,
    ) -> DocumentEmbeddingPipelineResult:
        assert self.calls is not None
        self.calls.append((document_id, chunk_version))
        if before_batch is not None:
            await before_batch()
        if self.error is not None:
            raise self.error
        return self.result


def test_processing_runs_chunking_before_embedding() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_pipeline = FakeChunkPipeline(
        result=DocumentChunkPipelineResult(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            chunk_count=4,
        )
    )
    embedding_pipeline = FakeEmbeddingPipeline(
        result=DocumentEmbeddingPipelineResult(
            document_id=document_id,
            provider="openai",
            model="text-embedding-example",
            dimensions=1536,
            embedded_chunk_count=4,
        )
    )
    service = DocumentProcessingService(
        chunk_pipeline=chunk_pipeline,  # type: ignore[arg-type]
        embedding_pipeline=embedding_pipeline,  # type: ignore[arg-type]
    )

    result = asyncio.run(
        service.process(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
    )

    assert chunk_pipeline.calls == [(knowledge_base_id, document_id)]
    assert embedding_pipeline.calls == [(document_id, 1)]
    assert result.document_id == document_id
    assert result.knowledge_base_id == knowledge_base_id
    assert result.chunk_count == 4
    assert result.embedded_chunk_count == 4
    assert result.embedding_provider == "openai"
    assert result.embedding_model == "text-embedding-example"
    assert result.embedding_dimensions == 1536


def test_processing_does_not_embed_when_chunking_fails() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_pipeline = FakeChunkPipeline(
        result=DocumentChunkPipelineResult(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            chunk_count=1,
        ),
        error=RuntimeError("chunking failed"),
    )
    embedding_pipeline = FakeEmbeddingPipeline(
        result=DocumentEmbeddingPipelineResult(
            document_id=document_id,
            provider="openai",
            model="model",
            dimensions=2,
            embedded_chunk_count=1,
        )
    )
    service = DocumentProcessingService(
        chunk_pipeline=chunk_pipeline,  # type: ignore[arg-type]
        embedding_pipeline=embedding_pipeline,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="chunking failed"):
        asyncio.run(
            service.process(
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
            )
        )

    assert embedding_pipeline.calls == []


def test_staged_processing_promotes_only_after_embedding() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    attempt_id = uuid4()
    chunk_pipeline = FakeChunkPipeline(
        result=DocumentChunkPipelineResult(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            chunk_count=2,
            version=2,
            attempt_id=attempt_id,
            reused_active=False,
        )
    )
    embedding_pipeline = FakeEmbeddingPipeline(
        result=DocumentEmbeddingPipelineResult(
            document_id=document_id,
            provider="fake",
            model="fixture",
            dimensions=3,
            embedded_chunk_count=2,
        )
    )
    service = DocumentProcessingService(
        chunk_pipeline=chunk_pipeline,  # type: ignore[arg-type]
        embedding_pipeline=embedding_pipeline,  # type: ignore[arg-type]
    )

    result = asyncio.run(
        service.process(knowledge_base_id=knowledge_base_id, document_id=document_id)
    )

    assert result.chunk_version == 2
    assert result.reused_active_version is False
    assert embedding_pipeline.calls == [(document_id, 2)]
    assert chunk_pipeline.events == ["renew", "promote"]


def test_staged_processing_records_failure_without_promotion() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    chunk_pipeline = FakeChunkPipeline(
        result=DocumentChunkPipelineResult(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            chunk_count=3,
            version=5,
            attempt_id=uuid4(),
            reused_active=False,
        )
    )
    embedding_pipeline = FakeEmbeddingPipeline(
        result=DocumentEmbeddingPipelineResult(
            document_id=document_id,
            provider="fake",
            model="fixture",
            dimensions=3,
            embedded_chunk_count=3,
        ),
        error=RuntimeError("provider down"),
    )
    service = DocumentProcessingService(
        chunk_pipeline=chunk_pipeline,  # type: ignore[arg-type]
        embedding_pipeline=embedding_pipeline,  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="provider down"):
        asyncio.run(service.process(knowledge_base_id=knowledge_base_id, document_id=document_id))

    assert embedding_pipeline.calls == [(document_id, 5)]
    assert chunk_pipeline.events == ["renew", "fail"]



def test_processing_explicit_options_select_chunker_without_mutating_legacy_default() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()

    class ConfigurableFakeChunkPipeline(FakeChunkPipeline):
        chosen_chunker: object | None = None

        async def run(self, *, knowledge_base_id: UUID, document_id: UUID, chunker=None):
            self.chosen_chunker = chunker
            return await super().run(
                knowledge_base_id=knowledge_base_id, document_id=document_id
            )

    chunk_pipeline = ConfigurableFakeChunkPipeline(
        result=DocumentChunkPipelineResult(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            chunk_count=1,
        )
    )
    embedding_pipeline = FakeEmbeddingPipeline(
        result=DocumentEmbeddingPipelineResult(
            document_id=document_id,
            provider="fake",
            model="model",
            dimensions=2,
            embedded_chunk_count=1,
        )
    )
    options = DocumentChunkOptions(
        strategy=ChunkStrategy.CHARACTERS, chunk_size=100, overlap=20
    )
    service = DocumentProcessingService(
        chunk_pipeline=chunk_pipeline,  # type: ignore[arg-type]
        embedding_pipeline=embedding_pipeline,  # type: ignore[arg-type]
        chunker_factory=lambda config: FixedSizeDocumentChunker(
            chunk_size=config.chunk_size, overlap=config.overlap
        ),
    )

    asyncio.run(
        service.process(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            chunk_options=options,
        )
    )
    assert isinstance(chunk_pipeline.chosen_chunker, FixedSizeDocumentChunker)

    asyncio.run(service.process(knowledge_base_id=knowledge_base_id, document_id=document_id))
    assert chunk_pipeline.chosen_chunker is None
