"""Smoke-check the localhost-only Spurel development stack."""

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _value(source: str, key: str, default: str = "") -> str:
    match = re.search(rf"(?m)^{re.escape(key)}=(.*)$", source)
    return os.getenv(key, match.group(1) if match else default)


def _status(url: str, *, token: str | None = None) -> int:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def check(root: Path) -> None:
    """Validate backend liveness, protected endpoint access and frontend HTTP."""
    content = (root / ".env").read_text(encoding="utf-8")
    token = _value(content, "SPUREL_API_TOKEN")
    if len(token) < 32:
        raise ValueError("SPUREL_API_TOKEN is missing or too short")

    api_port = int(_value(content, "SPUREL_API_PORT", "8000"))
    frontend_port = int(_value(content, "SPUREL_FRONTEND_PORT", "3000"))
    api = f"http://127.0.0.1:{api_port}"
    frontend = f"http://127.0.0.1:{frontend_port}"

    assert _status(api + "/health") == 200, "Backend health check failed"
    assert _status(api + "/knowledge-bases") == 401, "API is not enforcing bearer auth"
    assert _status(api + "/knowledge-bases", token=token) == 200, (
        "Authenticated API access or PostgreSQL migrations failed"
    )
    assert _status(frontend) == 200, "Frontend health check failed"
    assert _status(frontend + "/api/operator/session") == 200, (
        "Frontend operator session endpoint failed"
    )
    assert _status(frontend + "/api/workspace/knowledge-bases") == 401, (
        "Anonymous browser must not access the backend bearer proxy"
    )
    print(f"Spurel is ready: frontend {frontend}, backend {api}/health")


if __name__ == "__main__":
    try:
        check(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, AssertionError, urllib.error.URLError) as exc:
        print(f"Local stack check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
