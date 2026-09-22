"""FastAPI application entrypoint for Spurel."""

from fastapi import FastAPI

from spurel.api.health import router as health_router
from spurel.knowledge_bases.api import router as knowledge_base_router


def create_app() -> FastAPI:
    """Create and configure the Spurel FastAPI application."""
    application = FastAPI(
        title="Spurel API",
        version="0.1.0",
    )
    application.include_router(health_router)
    application.include_router(knowledge_base_router)
    return application


app = create_app()
