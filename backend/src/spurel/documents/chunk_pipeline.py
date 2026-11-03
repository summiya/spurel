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
    version: int = 1
    attempt_id: UUID | None = None
    reused_active: bool = True


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

        staging = await self._chunk_service.replace_for_document(
            document_id=ingestion.document_id,
            chunks=chunks,
        )

        return DocumentChunkPipelineResult(
            document_id=ingestion.document_id,
            knowledge_base_id=ingestion.knowledge_base_id,
            chunk_count=len(chunks),
            version=staging.version,
            attempt_id=staging.attempt_id,
            reused_active=staging.reused_active,
        )

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
        """Activate a staged version only after embedding coverage is verified."""
        await self._chunk_service.promote_version(
            document_id=document_id,
            version=version,
            attempt_id=attempt_id,
            provider=provider,
            model=model,
            dimensions=dimensions,
        )

    async def fail_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Fail a staged version without affecting its previous active index."""
        await self._chunk_service.fail_version(
            document_id=document_id, version=version, attempt_id=attempt_id
        )

    async def renew_version(
        self,
        *,
        document_id: UUID,
        version: int,
        attempt_id: UUID,
    ) -> None:
        """Refresh staging ownership before an embedding batch."""
        await self._chunk_service.renew_version(
            document_id=document_id, version=version, attempt_id=attempt_id
        )
