"""FastAPI application entrypoint for Spurel."""

from fastapi import FastAPI

from spurel.api.health import router as health_router
from spurel.documents.api import router as document_router
from spurel.evaluation_datasets.api import router as evaluation_dataset_router
from spurel.knowledge_bases.api import router as knowledge_base_router
from spurel.rag.api import router as rag_router
from spurel.retrieval.api import router as retrieval_router


def create_app() -> FastAPI:
    """Create and configure the Spurel FastAPI application."""
    application = FastAPI(
        title="Spurel API",
        version="0.1.0",
    )
    application.include_router(health_router)
    application.include_router(document_router)
    application.include_router(evaluation_dataset_router)
    application.include_router(knowledge_base_router)
    application.include_router(retrieval_router)
    application.include_router(rag_router)
    return application


app = create_app()
