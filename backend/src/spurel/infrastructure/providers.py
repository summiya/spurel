"""Explicit provider lifecycles used consistently by ingestion, retrieval, and RAG."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from openai import AsyncOpenAI

from spurel.embeddings.config import EmbeddingProviderConfig
from spurel.embeddings.domain import EmbeddingProvider
from spurel.generation.config import GenerationProviderConfig
from spurel.generation.ports import TextGenerationProvider
from spurel.infrastructure.embeddings.ollama import OllamaEmbeddingProvider
from spurel.infrastructure.embeddings.openai import OpenAIEmbeddingProvider
from spurel.infrastructure.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider
from spurel.infrastructure.generation.ollama import OllamaTextGenerationProvider
from spurel.infrastructure.generation.openai import OpenAITextGenerationProvider
from spurel.infrastructure.generation.openai_compatible import (
    OpenAICompatibleTextGenerationProvider,
)


def _compatible_client(*, api_key: str, base_url: str) -> AsyncOpenAI:
    """Disable environment proxies, redirects, and SDK retries for custom hosts."""
    transport = httpx.AsyncClient(
        timeout=120.0,
        follow_redirects=False,
        trust_env=False,
    )
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=0,
        http_client=transport,
    )


def _ollama_client(base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=120.0,
        follow_redirects=False,
        trust_env=False,
    )


@asynccontextmanager
async def embedding_provider_context(
    config: EmbeddingProviderConfig,
) -> AsyncIterator[EmbeddingProvider]:
    """Build only the operator-selected embedding adapter and dispose its client."""
    if config.provider == "ollama":
        assert config.base_url is not None
        async with _ollama_client(config.base_url) as client:
            yield OllamaEmbeddingProvider(
                client=client,
                model=config.model,
                dimensions=config.dimensions,
            )
        return

    assert config.api_key is not None
    if config.provider == "openai_compatible":
        assert config.base_url is not None
        sdk = _compatible_client(api_key=config.api_key, base_url=config.base_url)
    else:
        sdk = AsyncOpenAI(api_key=config.api_key)
    try:
        if config.provider == "openai_compatible":
            yield OpenAICompatibleEmbeddingProvider(
                client=sdk, model=config.model, dimensions=config.dimensions
            )
        else:
            yield OpenAIEmbeddingProvider(
                client=sdk, model=config.model, dimensions=config.dimensions
            )
    finally:
        await sdk.close()


@asynccontextmanager
async def generation_provider_context(
    config: GenerationProviderConfig,
) -> AsyncIterator[TextGenerationProvider]:
    """Build only the operator-selected text generator for explicit RAG calls."""
    if config.provider == "ollama":
        assert config.base_url is not None
        async with _ollama_client(config.base_url) as client:
            yield OllamaTextGenerationProvider(
                client=client,
                model=config.model,
                max_output_tokens=config.max_output_tokens,
            )
        return

    assert config.api_key is not None
    if config.provider == "openai_compatible":
        assert config.base_url is not None
        sdk = _compatible_client(api_key=config.api_key, base_url=config.base_url)
    else:
        sdk = AsyncOpenAI(api_key=config.api_key)
    try:
        if config.provider == "openai_compatible":
            yield OpenAICompatibleTextGenerationProvider(
                client=sdk, model=config.model, max_output_tokens=config.max_output_tokens
            )
        else:
            yield OpenAITextGenerationProvider(
                client=sdk, model=config.model, max_output_tokens=config.max_output_tokens
            )
    finally:
        await sdk.close()
