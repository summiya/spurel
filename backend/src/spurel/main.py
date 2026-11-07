"""FastAPI application entrypoint for Spurel."""

import os

from fastapi import Depends, FastAPI

from spurel.api.health import router as health_router
from spurel.documents.api import router as document_router
from spurel.evaluation_datasets.api import router as evaluation_dataset_router
from spurel.knowledge_bases.api import router as knowledge_base_router
from spurel.providers.api import router as provider_router
from spurel.rag.api import router as rag_router
from spurel.retrieval.api import router as retrieval_router
from spurel.security import require_api_token


def create_app() -> FastAPI:
    """Create and configure the Spurel FastAPI application."""
    enable_docs = os.getenv("SPUREL_ENABLE_DOCS") == "1"
    application = FastAPI(
        title="Spurel API",
        version="0.1.0",
        docs_url="/docs" if enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if enable_docs else None,
    )
    application.include_router(health_router)

    protected_routers = (
        document_router,
        evaluation_dataset_router,
        knowledge_base_router,
        retrieval_router,
        rag_router,
        provider_router,
    )
    for router in protected_routers:
        application.include_router(
            router,
            dependencies=[Depends(require_api_token)],
        )

    return application


app = create_app()
