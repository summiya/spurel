import pytest

from spurel.generation.config import (
    GenerationConfigurationError,
    OpenAIGenerationConfig,
)


def test_generation_config_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SPUREL_GENERATION_MODEL", "test-model")
    monkeypatch.setenv("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "900")

    config = OpenAIGenerationConfig.from_env()

    assert config.api_key == "test-key"
    assert config.model == "test-model"
    assert config.max_output_tokens == 900


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("OPENAI_API_KEY", ""),
        ("SPUREL_GENERATION_MODEL", ""),
        ("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "not-a-number"),
        ("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "0"),
        ("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "5000"),
    ],
)
def test_generation_config_rejects_invalid_environment(
    monkeypatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SPUREL_GENERATION_MODEL", "test-model")
    monkeypatch.setenv("SPUREL_GENERATION_MAX_OUTPUT_TOKENS", "900")
    monkeypatch.setenv(name, value)

    with pytest.raises(GenerationConfigurationError):
        OpenAIGenerationConfig.from_env()
