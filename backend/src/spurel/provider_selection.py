"""Strict server-only provider selection and trusted endpoint configuration."""

import os
from urllib.parse import urlsplit

PROVIDERS = frozenset({"openai", "openai_compatible", "ollama"})


class ProviderSelectionError(ValueError):
    """An operator-selected provider or endpoint is malformed."""


def provider_kind(environment_variable: str) -> str:
    """Read a fixed allowlist, with the original OpenAI provider as default."""
    value = os.getenv(environment_variable, "openai").strip().lower()
    if value not in PROVIDERS:
        raise ProviderSelectionError("unsupported model provider")
    return value


def trusted_endpoint(value: str, *, local: bool = False) -> str:
    """Allow explicit HTTP(S) origins without credentials or redirect targets.

    OpenAI-compatible hosts may have a versioned base path; Ollama uses its
    native /api routes and therefore must have no base path. These URLs
    originate ONLY from trusted server environment, never browser payloads.
    """
    raw = value.strip()
    if not raw or len(raw) > 2048 or any(ch.isspace() for ch in raw):
        raise ProviderSelectionError("provider endpoint is missing or invalid")
    try:
        parsed = urlsplit(raw)
        valid_port = parsed.port is None or 1 <= parsed.port <= 65535
    except ValueError as exc:
        raise ProviderSelectionError("provider endpoint is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or not valid_port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "//" in parsed.path
        or (local and parsed.path not in {"", "/"})
    ):
        raise ProviderSelectionError("provider endpoint is invalid")
    return raw.rstrip("/")
