import pytest

from spurel.embeddings.config import (
    EmbeddingConfigurationError,
    OpenAIEmbeddingConfig,
)


def test_openai_embedding_config_loads_valid_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", "text-embedding-example")
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", "1536")

    config = OpenAIEmbeddingConfig.from_env()

    assert config.api_key == "test-key"
    assert config.model == "text-embedding-example"
    assert config.dimensions == 1536


@pytest.mark.parametrize(
    ("key", "model", "dimensions"),
    [
        ("", "model", "1536"),
        ("key", "", "1536"),
        ("key", "model", ""),
        ("key", "model", "not-an-int"),
        ("key", "model", "0"),
    ],
)
def test_openai_embedding_config_rejects_invalid_environment(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    model: str,
    dimensions: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", key)
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", model)
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", dimensions)

    with pytest.raises(EmbeddingConfigurationError):
        OpenAIEmbeddingConfig.from_env()
