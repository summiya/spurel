"""SP-25 server-only provider choices fail closed and preserve legacy defaults."""

import pytest

from spurel.embeddings.config import (
    EmbeddingConfigurationError,
    EmbeddingProviderConfig,
)
from spurel.generation.config import (
    GenerationConfigurationError,
    GenerationProviderConfig,
)
from spurel.provider_selection import ProviderSelectionError, trusted_endpoint

_CONFIG_KEYS = (
    "SPUREL_EMBEDDING_PROVIDER",
    "SPUREL_GENERATION_PROVIDER",
    "SPUREL_EMBEDDING_BASE_URL",
    "SPUREL_GENERATION_BASE_URL",
    "SPUREL_EMBEDDING_API_KEY",
    "SPUREL_GENERATION_API_KEY",
    "SPUREL_OLLAMA_BASE_URL",
)


@pytest.fixture(autouse=True)
def _base_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _CONFIG_KEYS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "old-openai-key")
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", "1536")
    monkeypatch.setenv("SPUREL_GENERATION_MODEL", "gpt-test-model")
    monkeypatch.setenv("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "800")


def test_unmodified_env_preserves_original_openai_provider() -> None:
    embed = EmbeddingProviderConfig.from_env()
    generation = GenerationProviderConfig.from_env()
    assert (embed.provider, embed.api_key, embed.base_url, embed.dimensions) == (
        "openai",
        "old-openai-key",
        None,
        1536,
    )
    assert (generation.provider, generation.api_key, generation.base_url) == (
        "openai",
        "old-openai-key",
        None,
    )


def test_hosted_compatible_endpoints_require_explicit_keys_and_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("SPUREL_GENERATION_PROVIDER", "openai_compatible")
    monkeypatch.setenv("SPUREL_EMBEDDING_BASE_URL", "https://embed.example/v1")
    monkeypatch.setenv("SPUREL_GENERATION_BASE_URL", "https://chat.example/api/v1")
    monkeypatch.setenv("SPUREL_EMBEDDING_API_KEY", "embedding-secret")
    monkeypatch.setenv("SPUREL_GENERATION_API_KEY", "generation-secret")
    assert EmbeddingProviderConfig.from_env().provider == "openai_compatible"
    assert EmbeddingProviderConfig.from_env().api_key == "embedding-secret"
    assert GenerationProviderConfig.from_env().base_url == "https://chat.example/api/v1"

    monkeypatch.delenv("SPUREL_GENERATION_API_KEY")
    with pytest.raises(GenerationConfigurationError):
        GenerationProviderConfig.from_env()
    monkeypatch.delenv("SPUREL_EMBEDDING_API_KEY")
    with pytest.raises(EmbeddingConfigurationError):
        EmbeddingProviderConfig.from_env()


def test_ollama_is_explicit_and_does_not_require_cloud_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("SPUREL_GENERATION_PROVIDER", "ollama")
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", "nomic-embed-text")
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", "768")
    monkeypatch.setenv("SPUREL_GENERATION_MODEL", "llama3")
    monkeypatch.setenv("SPUREL_OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    monkeypatch.delenv("OPENAI_API_KEY")
    embed = EmbeddingProviderConfig.from_env()
    generation = GenerationProviderConfig.from_env()
    assert (embed.provider, embed.dimensions, embed.api_key) == ("ollama", 768, None)
    assert (generation.provider, generation.api_key) == ("ollama", None)
    assert embed.base_url == generation.base_url


@pytest.mark.parametrize(
    "value",
    [
        "ftp://remote",
        "http://api.some-public-host.example/v1",
        "http://user:pass@example.test",
        "http://example.test?token=x",
        "http://example.test/#secret",
        "http://example.test:99999",
        "http://",
        "https://some host.test",
        "file:///etc/passwd",
    ],
)
def test_provider_urls_reject_unsafe_or_malformed_values(value: str) -> None:
    with pytest.raises(ProviderSelectionError):
        trusted_endpoint(value)


def test_ollama_url_requires_origin_without_versioned_path() -> None:
    with pytest.raises(ProviderSelectionError):
        trusted_endpoint("http://localhost:11434/api/embed", local=True)
    assert trusted_endpoint("http://localhost:11434/", local=True) == "http://localhost:11434"


def test_unknown_provider_does_not_fall_back_to_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_EMBEDDING_PROVIDER", "not-a-provider")
    with pytest.raises(EmbeddingConfigurationError):
        EmbeddingProviderConfig.from_env()
    monkeypatch.setenv("SPUREL_GENERATION_PROVIDER", "not-a-provider")
    with pytest.raises(GenerationConfigurationError):
        GenerationProviderConfig.from_env()


def test_provider_output_dimensions_and_token_count_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("SPUREL_OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", "bad")
    with pytest.raises(EmbeddingConfigurationError):
        EmbeddingProviderConfig.from_env()
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", "768")
    assert EmbeddingProviderConfig.from_env().dimensions == 768
    monkeypatch.setenv("SPUREL_GENERATION_PROVIDER", "ollama")
    monkeypatch.setenv("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "5000")
    with pytest.raises(GenerationConfigurationError):
        GenerationProviderConfig.from_env()
