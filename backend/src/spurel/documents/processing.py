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

        embedding_result = await self._embedding_pipeline.run(
            document_id=chunk_result.document_id,
        )

        return DocumentProcessingResult(
            document_id=chunk_result.document_id,
            knowledge_base_id=chunk_result.knowledge_base_id,
            chunk_count=chunk_result.chunk_count,
            embedded_chunk_count=embedding_result.embedded_chunk_count,
            embedding_provider=embedding_result.provider,
            embedding_model=embedding_result.model,
            embedding_dimensions=embedding_result.dimensions,
        )
