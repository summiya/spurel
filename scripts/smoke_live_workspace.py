"""CI-only smoke of protected source, retrieval and saved trace workflows."""

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
    list_status, listed_bases = _request(opener, base, endpoint)
    assert list_status == 200, ("Authenticated KB list", list_status, listed_bases)

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

    # SP-11: unprocessed documents have no active chunks or saved versions.
    # Verify the real read-only routes without spending on an embedding provider.
    doc_id = str(UUID(document["id"]))
    versions_path = f"{document_path}/{doc_id}/versions"
    chunks_path = f"{document_path}/{doc_id}/chunks"
    version_status, version_data = _request(opener, base, versions_path)
    assert version_status == 200, ("Version history", version_status, version_data)
    assert version_data["items"] == [], version_data

    active_status, active_data = _request(opener, base, chunks_path)
    assert active_status == 200, ("Current chunks", active_status, active_data)
    assert active_data["items"] == [], active_data

    assert _request(opener, base, chunks_path + "?version=0")[0] == 400
    assert _request(opener, base, chunks_path + "?offset=-1")[0] == 400
    assert _request(opener, base, f"{document_path}/invalid-id/versions")[0] == 400
    assert _request(opener, base, chunks_path + "?version=1")[0] == 404

    # SP-12: keyword is a real PostgreSQL full-text query with no OpenAI calls.
    # The newly uploaded document is unindexed, so a valid empty result is expected.
    retrieval_root = f"{endpoint}/{kb_id}/retrieval"
    keyword_endpoint = f"{retrieval_root}/keyword"
    keyword_payload = json.dumps({"query": "Smoke-test document", "top_k": 10}).encode("utf-8")

    assert _request(opener, base, keyword_endpoint, method="POST", data=keyword_payload,
                    content_type="application/json", origin="http://untrusted.example")[0] == 403
    assert _request(opener, base, f"{retrieval_root}/rerank", method="POST", data=keyword_payload,
                    content_type="application/json", origin=base)[0] == 400
    assert _request(opener, base, keyword_endpoint, method="POST",
                    data=b'{"query":"x","top_k":0}', content_type="application/json",
                    origin=base)[0] == 422
    assert _request(opener, base, f"{retrieval_root}/hybrid", method="POST",
                    data=b'{"query":"x","top_k":10,"candidate_k":5,"rrf_k":60}',
                    content_type="application/json", origin=base)[0] == 422

    status, retrieval = _request(
        opener, base, keyword_endpoint, method="POST", data=keyword_payload,
        content_type="application/json", origin=base,
    )
    assert status == 200, (status, retrieval)
    assert retrieval["mode"] == "keyword"
    assert retrieval["query"] == "Smoke-test document"
    assert retrieval["matches"] == []
    assert retrieval["duration_ms"] >= 0
    trace_id = str(UUID(retrieval["trace_id"]))
    trace_path = f"{retrieval_root}/traces/{trace_id}"
    status, trace = _request(opener, base, trace_path)
    assert status == 200, (status, trace)
    assert trace["id"] == trace_id
    assert trace["mode"] == "keyword"
    assert trace["results"] == []
    assert trace["embedding_provider"] is None
    assert _request(opener, base, f"{retrieval_root}/traces/invalid-id")[0] == 400

    # SP-13: read actual newest-first persisted trace history and compare
    # two real saved keyword traces without any provider requests.
    keyword_payload_b = json.dumps({"query": "A different retention question", "top_k": 10}).encode(
        "utf-8"
    )
    second_status, second_retrieval = _request(
        opener, base, keyword_endpoint, method="POST", data=keyword_payload_b,
        content_type="application/json", origin=base,
    )
    assert second_status == 200, (second_status, second_retrieval)
    second_trace_id = str(UUID(second_retrieval["trace_id"]))
    assert second_trace_id != trace_id

    history_endpoint = f"{retrieval_root}/traces"
    hist_status, history = _request(opener, base, history_endpoint)
    assert hist_status == 200, (hist_status, history)
    stored_ids = [entry["id"] for entry in history["items"]]
    assert trace_id in stored_ids and second_trace_id in stored_ids
    assert history["items"][0]["id"] == second_trace_id
    assert _request(opener, base, history_endpoint + "?offset=-1")[0] == 400
    assert _request(opener, base, f"{endpoint}/invalid-id/retrieval/traces")[0] == 400

    comparison_endpoint = f"{retrieval_root}/trace-comparisons"
    comparison_payload = json.dumps({
        "first_trace_id": trace_id,
        "second_trace_id": second_trace_id,
    }).encode("utf-8")
    assert _request(
        opener, base, comparison_endpoint, method="POST", data=comparison_payload,
        content_type="application/json", origin="http://untrusted.example",
    )[0] == 403
    assert _request(
        opener, base, comparison_endpoint, method="POST",
        data=json.dumps({"first_trace_id": trace_id, "second_trace_id": trace_id}).encode("utf-8"),
        content_type="application/json", origin=base,
    )[0] == 422

    comparison_status, comparison = _request(
        opener, base, comparison_endpoint, method="POST", data=comparison_payload,
        content_type="application/json", origin=base,
    )
    assert comparison_status == 200, (comparison_status, comparison)
    assert comparison["first"]["trace_id"] == trace_id
    assert comparison["second"]["trace_id"] == second_trace_id
    assert comparison["same_query"] is False
    assert comparison["overlap_count"] == comparison["union_count"] == 0
    assert comparison["overlap_ratio"] is None
    assert comparison["results"] == []
    assert isinstance(comparison["duration_delta_ms"], (float, int))

    # SP-15: exercise the exact RAG frontend proxy without calling a paid provider.
    # Valid requests are intentionally only sent from a rejected origin or after logout.
    rag_endpoint = f"{endpoint}/{kb_id}/rag/answer"
    rag_payload = json.dumps(
        {"query": "What is the policy?", "top_k": 8, "candidate_k": 50, "rrf_k": 60}
    ).encode("utf-8")
    assert _request(
        opener,
        base,
        rag_endpoint,
        method="POST",
        data=rag_payload,
        content_type="application/json",
        origin="http://untrusted.example",
    )[0] == 403
    assert _request(
        opener,
        base,
        rag_endpoint,
        method="POST",
        data=b'{"query":"","top_k":8,"candidate_k":50,"rrf_k":60}',
        content_type="application/json",
        origin=base,
    )[0] == 422
    assert _request(
        opener,
        base,
        rag_endpoint,
        method="POST",
        data=b'{"query":"x","top_k":21,"candidate_k":50,"rrf_k":60}',
        content_type="application/json",
        origin=base,
    )[0] == 422
    assert _request(
        opener,
        base,
        rag_endpoint,
        method="POST",
        data=b'not-json',
        content_type="application/json",
        origin=base,
    )[0] == 400
    assert _request(
        opener,
        base,
        f"{endpoint}/invalid-id/rag/answer",
        method="POST",
        data=rag_payload,
        content_type="application/json",
        origin=base,
    )[0] == 400

    status, _ = _request(opener, base, "/api/operator/logout", method="POST", data=b"", origin=base)
    assert status == 200
    assert _request(opener, base, endpoint)[0] == 401
    assert _request(opener, base, versions_path)[0] == 401
    assert _request(opener, base, chunks_path)[0] == 401
    assert _request(opener, base, trace_path)[0] == 401
    assert _request(opener, base, keyword_endpoint, method="POST", data=keyword_payload,
                    content_type="application/json", origin=base)[0] == 401
    assert _request(opener, base, history_endpoint)[0] == 401
    assert _request(opener, base, comparison_endpoint, method="POST", data=comparison_payload,
                    content_type="application/json", origin=base)[0] == 401
    assert _request(
        opener,
        base,
        rag_endpoint,
        method="POST",
        data=rag_payload,
        content_type="application/json",
        origin=base,
    )[0] == 401
    print(
        "SP-13/SP-15 operator auth, real retrieval/trace workflows, "
        "RAG proxy rejection checks and CSRF: PASS (no provider calls)"
    )


if __name__ == "__main__":
    try:
        run(Path(__file__).resolve().parents[1])
    except Exception as exc:
        print(f"Spurel workspace smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
