"""OpenAI implementation of the provider-independent embedding contract."""

from collections.abc import Sequence

from openai import AsyncOpenAI

from spurel.embeddings.domain import (
    EmbeddingBatch,
    EmbeddingProviderError,
    EmbeddingResultError,
    validate_embedding_dimensions,
    validate_embedding_inputs,
)


class OpenAIEmbeddingProvider:
    """Embed text with OpenAI while returning Spurel domain values only."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        model: str,
        dimensions: int,
    ) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise EmbeddingResultError(
                "embedding model identifier must not be empty"
            )

        validate_embedding_dimensions(dimensions)

        self._client = client
        self._model = normalized_model
        self._dimensions = dimensions

    @property
    def model(self) -> str:
        """Return the configured OpenAI embedding model."""
        return self._model

    @property
    def dimensions(self) -> int:
        """Return the configured embedding dimensions."""
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Embed a validated ordered text batch."""
        normalized_texts = validate_embedding_inputs(texts)

        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=list(normalized_texts),
                dimensions=self._dimensions,
                encoding_format="float",
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                "OpenAI embedding request failed"
            ) from exc

        if len(response.data) != len(normalized_texts):
            raise EmbeddingResultError(
                "OpenAI returned an unexpected embedding count"
            )

        ordered = sorted(response.data, key=lambda item: item.index)
        expected_indexes = list(range(len(normalized_texts)))
        actual_indexes = [item.index for item in ordered]

        if actual_indexes != expected_indexes:
            raise EmbeddingResultError(
                "OpenAI returned invalid embedding indexes"
            )

        return EmbeddingBatch.create(
            vectors=[item.embedding for item in ordered],
            input_count=len(normalized_texts),
            model=self._model,
            dimensions=self._dimensions,
        )
