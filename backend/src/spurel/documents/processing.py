"""Application orchestration for complete document processing."""

from dataclasses import dataclass
from uuid import UUID

from spurel.documents.chunk_pipeline import DocumentChunkPipeline
from spurel.embeddings.pipeline import DocumentEmbeddingPipeline


@dataclass(frozen=True, slots=True)
class DocumentProcessingResult:
    """Summary of one fully processed document."""

    document_id: UUID
    knowledge_base_id: UUID
    chunk_count: int
    embedded_chunk_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    chunk_version: int = 1
    reused_active_version: bool = False


class DocumentProcessingService:
    """Run chunking and embedding stages for one persisted document."""

    def __init__(
        self,
        *,
        chunk_pipeline: DocumentChunkPipeline,
        embedding_pipeline: DocumentEmbeddingPipeline,
    ) -> None:
        self._chunk_pipeline = chunk_pipeline
        self._embedding_pipeline = embedding_pipeline

    async def process(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> DocumentProcessingResult:
        """Parse, chunk, persist, embed, and index one document."""
        chunk_result = await self._chunk_pipeline.run(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )

        try:
            embedding_result = await self._embedding_pipeline.run(
                document_id=chunk_result.document_id,
                chunk_version=chunk_result.version,
                before_batch=(
                    (
                        lambda: self._chunk_pipeline.renew_version(
                            document_id=chunk_result.document_id,
                            version=chunk_result.version,
                            attempt_id=chunk_result.attempt_id,
                        )
                    )
                    if chunk_result.attempt_id is not None
                    else None
                ),
            )

            if chunk_result.attempt_id is not None:
                await self._chunk_pipeline.promote_version(
                    document_id=chunk_result.document_id,
                    version=chunk_result.version,
                    attempt_id=chunk_result.attempt_id,
                    provider=embedding_result.provider,
                    model=embedding_result.model,
                    dimensions=embedding_result.dimensions,
                )
        except Exception:
            if chunk_result.attempt_id is not None:
                await self._chunk_pipeline.fail_version(
                    document_id=chunk_result.document_id,
                    version=chunk_result.version,
                    attempt_id=chunk_result.attempt_id,
                )
            raise

        return DocumentProcessingResult(
            document_id=chunk_result.document_id,
            knowledge_base_id=chunk_result.knowledge_base_id,
            chunk_count=chunk_result.chunk_count,
            embedded_chunk_count=embedding_result.embedded_chunk_count,
            embedding_provider=embedding_result.provider,
            embedding_model=embedding_result.model,
            embedding_dimensions=embedding_result.dimensions,
            chunk_version=chunk_result.version,
            reused_active_version=chunk_result.reused_active,
        )
