"""CI-only end-to-end check of local operator auth, knowledge bases and upload."""

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID, uuid4


def _env(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
    )


def _request(
    opener: urllib.request.OpenerDirector,
    base: str,
    route: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    content_type: str | None = None,
    origin: str | None = None,
) -> tuple[int, dict]:
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(
        base + route,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with opener.open(req, timeout=30) as result:
            return result.status, json.load(result)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def run(root: Path) -> None:
    config = _env(root / ".env")
    password = config["SPUREL_FRONTEND_OPERATOR_PASSWORD"]
    assert len(password) >= 32
    port = int(config.get("SPUREL_FRONTEND_PORT", "3000"))
    base = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    endpoint = "/api/workspace/knowledge-bases"

    assert _request(opener, base, endpoint)[0] == 401
    assert _request(opener, base, "/api/operator/session")[1] == {
        "configured": True,
        "authenticated": False,
    }

    invalid = json.dumps({"password": "invalid"}).encode("utf-8")
    denied_status, _ = _request(
        opener, base, "/api/operator/login", method="POST", data=invalid,
        content_type="application/json", origin=base,
    )
    assert denied_status == 401, f"Invalid password expected HTTP 401; got {denied_status}"

    credentials = json.dumps({"password": password}).encode("utf-8")
    assert _request(
        opener, base, "/api/operator/login", method="POST", data=credentials,
        content_type="application/json", origin="http://untrusted.example",
    )[0] == 403
    status, _ = _request(
        opener, base, "/api/operator/login", method="POST", data=credentials,
        content_type="application/json", origin=base,
    )
    assert status == 200
    assert _request(opener, base, endpoint)[0] == 200

    kb_name = "SP-10 smoke " + uuid4().hex[:8]
    status, kb = _request(
        opener, base, endpoint, method="POST",
        data=json.dumps({"name": kb_name}).encode("utf-8"),
        content_type="application/json", origin=base,
    )
    assert status == 201, (status, kb)
    assert kb["name"] == kb_name
    kb_id = str(UUID(kb["id"]))

    # Mutation blocked for cross-origin callers, even with a valid session.
    assert _request(
        opener, base, endpoint, method="POST",
        data=b'{"name":"rejected"}', content_type="application/json",
        origin="http://untrusted.example",
    )[0] == 403

    document_path = f"{endpoint}/{kb_id}/documents"
    boundary = "----spurel-ci-boundary"
    payload = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="ci-sample.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "Smoke-test upload of an actual document.\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    status, document = _request(
        opener, base, document_path, method="POST",
        data=payload, content_type=f"multipart/form-data; boundary={boundary}", origin=base,
    )
    assert status == 201, (status, document)
    assert document["active_chunk_version"] == 0
    assert document["filename"] == "ci-sample.txt"
    status, listed = _request(opener, base, document_path)
    assert status == 200
    assert any(item["id"] == document["id"] for item in listed["items"])

    status, _ = _request(opener, base, "/api/operator/logout", method="POST", data=b"", origin=base)
    assert status == 200
    assert _request(opener, base, endpoint)[0] == 401
    print("SP-10 operator session, CSRF, real KB creation and document upload: PASS")


if __name__ == "__main__":
    try:
        run(Path(__file__).resolve().parents[1])
    except Exception as exc:
        print(f"SP-10 smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
