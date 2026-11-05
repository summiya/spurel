"""Bounded OpenAI-compatible embeddings with strict returned-space validation."""

from openai import AsyncOpenAI

from spurel.infrastructure.embeddings.openai import OpenAIEmbeddingProvider


class OpenAICompatibleEmbeddingProvider(OpenAIEmbeddingProvider):
    """OpenAI-compatible embedding endpoint without dimensions request override."""

    def __init__(self, *, client: AsyncOpenAI, model: str, dimensions: int) -> None:
        super().__init__(
            client=client,
            model=model,
            dimensions=dimensions,
            include_dimensions=False,
        )

    @property
    def provider(self) -> str:
        return "openai_compatible"
