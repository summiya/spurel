"""Read-only, operator-authenticated model configuration metadata.

Never expose credentials, endpoint URLs, probes or remote provider output.
"""

import os

from fastapi import APIRouter
from pydantic import BaseModel

from spurel.embeddings.config import EmbeddingConfigurationError, EmbeddingProviderConfig
from spurel.generation.config import GenerationConfigurationError, GenerationProviderConfig
from spurel.provider_selection import ProviderSelectionError, provider_kind

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderState(BaseModel):
    provider: str
    model: str | None
    configured: bool
    dimensions: int | None = None


class ProviderStatusResponse(BaseModel):
    embedding: ProviderState
    generation: ProviderState


def _selected(name: str) -> str:
    try:
        return provider_kind(name)
    except ProviderSelectionError:
        return "invalid"


def _safe_model(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value if 0 < len(value) <= 255 else None


@router.get("/status", response_model=ProviderStatusResponse)
def provider_status() -> ProviderStatusResponse:
    """Report config presence, not whether a model server is reachable."""
    try:
        embedding = EmbeddingProviderConfig.from_env()
        embedding_state = ProviderState(
            provider=embedding.provider,
            model=embedding.model,
            configured=True,
            dimensions=embedding.dimensions,
        )
    except EmbeddingConfigurationError:
        embedding_state = ProviderState(
            provider=_selected("SPUREL_EMBEDDING_PROVIDER"),
            model=_safe_model("SPUREL_EMBEDDING_MODEL"),
            configured=False,
        )

    try:
        generation = GenerationProviderConfig.from_env()
        generation_state = ProviderState(
            provider=generation.provider,
            model=generation.model,
            configured=True,
        )
    except GenerationConfigurationError:
        generation_state = ProviderState(
            provider=_selected("SPUREL_GENERATION_PROVIDER"),
            model=_safe_model("SPUREL_GENERATION_MODEL"),
            configured=False,
        )
    return ProviderStatusResponse(embedding=embedding_state, generation=generation_state)
