"""Application orchestration from persisted document to persisted chunks."""

from dataclasses import dataclass
from uuid import UUID

from spurel.documents.chunk_service import DocumentChunkService
from spurel.documents.chunking import DocumentChunker
from spurel.documents.ingestion_service import DocumentIngestionService


@dataclass(frozen=True, slots=True)
class DocumentChunkPipelineResult:
    """Summary of one successful document chunking run."""

    document_id: UUID
    knowledge_base_id: UUID
    chunk_count: int


class DocumentChunkPipeline:
    """Parse, chunk, and atomically persist one document's chunk set."""

    def __init__(
        self,
        *,
        ingestion_service: DocumentIngestionService,
        chunker: DocumentChunker,
        chunk_service: DocumentChunkService,
    ) -> None:
        self._ingestion_service = ingestion_service
        self._chunker = chunker
        self._chunk_service = chunk_service

    async def run(
        self,
        *,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> DocumentChunkPipelineResult:
        """Run the document through parse, chunk, and persistence stages."""
        ingestion = await self._ingestion_service.ingest(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )

        chunks = self._chunker.chunk(text=ingestion.parsed.text)

        await self._chunk_service.replace_for_document(
            document_id=ingestion.document_id,
            chunks=chunks,
        )

        return DocumentChunkPipelineResult(
            document_id=ingestion.document_id,
            knowledge_base_id=ingestion.knowledge_base_id,
            chunk_count=len(chunks),
        )
