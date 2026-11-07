"""OpenAI-compatible Chat Completions adapter for hosted model services."""

from openai import AsyncOpenAI

from spurel.generation.domain import (
    TextGenerationRequest,
    TextGenerationResult,
    TextGenerationResultError,
)
from spurel.generation.ports import TextGenerationProviderError


class OpenAICompatibleTextGenerationProvider:
    """Generate text via the Chat Completions API, not the Responses API."""

    def __init__(self, *, client: AsyncOpenAI, model: str, max_output_tokens: int) -> None:
        if not model.strip() or max_output_tokens < 1 or isinstance(max_output_tokens, bool):
            raise TextGenerationResultError("compatible generation configuration is invalid")
        self._client = client
        self._model = model.strip()
        self._max_output_tokens = max_output_tokens

    @property
    def provider(self) -> str:
        return "openai_compatible"

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        request.validate()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                max_tokens=self._max_output_tokens,
            )
        except Exception as exc:
            raise TextGenerationProviderError("compatible generation request failed") from exc
        if len(response.choices) != 1 or not isinstance(response.choices[0].message.content, str):
            raise TextGenerationResultError("compatible generation response is invalid")
        result = TextGenerationResult(
            provider=self.provider,
            model=self._model,
            text=response.choices[0].message.content.strip(),
        )
        result.validate()
        return result
