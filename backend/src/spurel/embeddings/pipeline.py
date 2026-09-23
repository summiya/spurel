"""Application orchestration from persisted chunks to stored embeddings."""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from spurel.documents.chunk_models import StoredDocumentChunk
from spurel.documents.chunk_ports import StoredDocumentChunkReader
from spurel.embeddings.chunk import ChunkEmbedding
from spurel.embeddings.domain import (
    MAX_EMBEDDING_BATCH_SIZE,
    EmbeddingProvider,
    EmbeddingVector,
)
from spurel.embeddings.service import ChunkEmbeddingService


class DocumentEmbeddingPipelineError(RuntimeError):
    """Base error for document embedding orchestration."""


class DocumentEmbeddingPipelineConfigError(DocumentEmbeddingPipelineError):
    """Raised when embedding pipeline configuration is invalid."""


class DocumentEmbeddingNoChunksError(DocumentEmbeddingPipelineError):
    """Raised when a document has no persisted chunks to embed."""


class DocumentEmbeddingProviderContractError(DocumentEmbeddingPipelineError):
    """Raised when provider output conflicts with its advertised contract."""


@dataclass(frozen=True, slots=True)
class DocumentEmbeddingPipelineResult:
    """Summary of one successful document embedding run."""

    document_id: UUID
    provider: str
    model: str
    dimensions: int
    embedded_chunk_count: int


class DocumentEmbeddingPipeline:
    """Page persisted chunks through an embedding provider and persistence service."""

    def __init__(
        self,
        *,
        chunk_reader: StoredDocumentChunkReader,
        provider: EmbeddingProvider,
        embedding_service: ChunkEmbeddingService,
        batch_size: int = MAX_EMBEDDING_BATCH_SIZE,
    ) -> None:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size < 1
            or batch_size > MAX_EMBEDDING_BATCH_SIZE
        ):
            raise DocumentEmbeddingPipelineConfigError(
                "embedding pipeline batch size is outside the supported range"
            )

        self._chunk_reader = chunk_reader
        self._provider = provider
        self._embedding_service = embedding_service
        self._batch_size = batch_size

    async def run(
        self,
        *,
        document_id: UUID,
    ) -> DocumentEmbeddingPipelineResult:
        """Embed all persisted chunks for one document in bounded batches."""
        offset = 0
        embedded_chunk_count = 0

        while True:
            chunks = await self._chunk_reader.list_stored_by_document(
                document_id=document_id,
                limit=self._batch_size,
                offset=offset,
            )

            if not chunks:
                if embedded_chunk_count == 0:
                    raise DocumentEmbeddingNoChunksError(
                        "document has no persisted chunks"
                    )
                break

            batch = await self._provider.embed(
                [stored.chunk.text for stored in chunks]
            )
            self._validate_provider_contract(
                batch_model=batch.model,
                batch_dimensions=batch.dimensions,
            )

            embeddings = _build_chunk_embeddings(
                chunks=chunks,
                provider=self._provider.provider,
                model=batch.model,
                vectors=batch.vectors,
            )
            await self._embedding_service.upsert_batch(embeddings)

            processed = len(chunks)
            embedded_chunk_count += processed
            offset += processed

            if processed < self._batch_size:
                break

        return DocumentEmbeddingPipelineResult(
            document_id=document_id,
            provider=self._provider.provider,
            model=self._provider.model,
            dimensions=self._provider.dimensions,
            embedded_chunk_count=embedded_chunk_count,
        )

    def _validate_provider_contract(
        self,
        *,
        batch_model: str,
        batch_dimensions: int,
    ) -> None:
        if batch_model != self._provider.model:
            raise DocumentEmbeddingProviderContractError(
                "embedding provider returned an unexpected model"
            )

        if batch_dimensions != self._provider.dimensions:
            raise DocumentEmbeddingProviderContractError(
                "embedding provider returned unexpected dimensions"
            )


def _build_chunk_embeddings(
    *,
    chunks: Sequence[StoredDocumentChunk],
    provider: str,
    model: str,
    vectors: Sequence[EmbeddingVector],
) -> tuple[ChunkEmbedding, ...]:
    return tuple(
        ChunkEmbedding.create(
            chunk_id=stored.id,
            provider=provider,
            model=model,
            vector=vector,
        )
        for stored, vector in zip(chunks, vectors, strict=True)
    )
