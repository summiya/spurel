import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from spurel.documents.chunk_pipeline import DocumentChunkPipelineResult
from spurel.documents.processing import DocumentProcessingService
from spurel.embeddings.pipeline import DocumentEmbeddingPipelineResult


@dataclass
class FakeChunkPipeline:
    result: DocumentChunkPipelineResult
    error: Exception | None = None
    calls: list[tuple[UUID, UUID]] | None = None

    def __post_init__(self) -> None:
        self.calls = []

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
    calls: list[UUID] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    async def run(
        self,
        *,
        document_id: UUID,
    ) -> DocumentEmbeddingPipelineResult:
        assert self.calls is not None
        self.calls.append(document_id)
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
    assert embedding_pipeline.calls == [document_id]
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
