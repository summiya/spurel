"""Native Ollama /api/chat generation adapter with no implicit model pull."""

import httpx

from spurel.generation.domain import (
    TextGenerationRequest,
    TextGenerationResult,
    TextGenerationResultError,
)
from spurel.generation.ports import TextGenerationProviderError


class OllamaTextGenerationProvider:
    """Generate non-streaming text through an operator-hosted Ollama service."""

    def __init__(self, *, client: httpx.AsyncClient, model: str, max_output_tokens: int) -> None:
        if not model.strip() or max_output_tokens < 1 or isinstance(max_output_tokens, bool):
            raise TextGenerationResultError("Ollama generation configuration is invalid")
        self._client = client
        self._model = model.strip()
        self._max_output_tokens = max_output_tokens

    @property
    def provider(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        request.validate()
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": request.user_prompt},
                    ],
                    "stream": False,
                    "options": {"num_predict": self._max_output_tokens},
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TextGenerationProviderError("Ollama generation request failed") from exc
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("message"), dict)
            or not isinstance(payload["message"].get("content"), str)
        ):
            raise TextGenerationResultError("Ollama generation response is invalid")
        result = TextGenerationResult(
            provider=self.provider,
            model=self._model,
            text=payload["message"]["content"].strip(),
        )
        result.validate()
        return result
