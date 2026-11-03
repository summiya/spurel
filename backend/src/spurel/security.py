"""Shared bearer-token authentication for protected Spurel API routes."""

import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_MIN_API_TOKEN_LENGTH = 32
_bearer_scheme = HTTPBearer(auto_error=False)


def require_api_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> None:
    """Fail closed without a strong configured token; reject unauthorized callers."""
    configured_token = os.getenv("SPUREL_API_TOKEN", "")

    if (
        len(configured_token) < _MIN_API_TOKEN_LENGTH
        or not configured_token.isascii()
        or not configured_token.isprintable()
        or any(character.isspace() for character in configured_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )

    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"),
        configured_token.encode("ascii"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
