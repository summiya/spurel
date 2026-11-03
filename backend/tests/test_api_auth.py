"""Security regression tests for the shared API bearer-token boundary."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from spurel.knowledge_bases.dependencies import get_knowledge_base_service
from spurel.main import create_app

_TEST_TOKEN = "spurel-security-test-token-with-at-least-32-characters"


class FakeKnowledgeBaseService:
    async def list(self, *, limit: int, offset: int) -> tuple:
        return ()


def test_health_is_public_without_auth_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPUREL_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_api_fails_closed_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPUREL_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/knowledge-bases")

    assert response.status_code == 503
    assert response.json() == {"detail": "API authentication is not configured"}


@pytest.mark.parametrize(
    "configured_token",
    ["", "short-token", "x" * 31, "x" * 32 + " ", "x" * 32 + "\n"],
)
def test_invalid_server_tokens_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    configured_token: str,
) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", configured_token)
    client = TestClient(create_app())

    response = client.get("/knowledge-bases", headers={"Authorization": "Bearer anything"})

    assert response.status_code == 503


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer wrong-token", "Basic test", "Token something", "Bearer"],
)
def test_missing_or_invalid_credentials_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    authorization: str | None,
) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", _TEST_TOKEN)
    client = TestClient(create_app())
    headers = {"Authorization": authorization} if authorization is not None else {}

    response = client.get("/knowledge-bases", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing bearer token"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_valid_token_allows_normal_api_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", _TEST_TOKEN)
    application = create_app()
    application.dependency_overrides[get_knowledge_base_service] = lambda: (
        FakeKnowledgeBaseService()
    )
    client = TestClient(application)

    response = client.get(
        "/knowledge-bases",
        headers={"Authorization": f"Bearer {_TEST_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_business_write_endpoints_require_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", _TEST_TOKEN)
    knowledge_base_id = uuid4()
    client = TestClient(create_app())

    write_requests = (
        ("/knowledge-bases", {"name": "Private Docs"}),
        (
            f"/knowledge-bases/{knowledge_base_id}/documents/{uuid4()}/process",
            None,
        ),
        (
            f"/knowledge-bases/{knowledge_base_id}/retrieval/hybrid",
            {"query": "private"},
        ),
        (
            f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets",
            {"name": "Private Evaluation"},
        ),
        (
            f"/knowledge-bases/{knowledge_base_id}/rag/answer",
            {"query": "private"},
        ),
    )
    for path, payload in write_requests:
        response = client.post(path, json=payload)
        assert response.status_code == 401, path


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_documentation_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.delenv("SPUREL_ENABLE_DOCS", raising=False)
    client = TestClient(create_app())

    assert client.get(path).status_code == 404


def test_docs_can_be_explicitly_enabled_for_local_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_ENABLE_DOCS", "1")
    monkeypatch.setenv("SPUREL_API_TOKEN", _TEST_TOKEN)
    client = TestClient(create_app())

    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/knowledge-bases"]["get"]["security"]
    assert client.get("/knowledge-bases").status_code == 401


def test_all_business_route_groups_reject_anonymous_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", _TEST_TOKEN)
    knowledge_base_id = uuid4()
    paths = (
        "/knowledge-bases",
        f"/knowledge-bases/{knowledge_base_id}/documents",
        f"/knowledge-bases/{knowledge_base_id}/retrieval/traces",
        f"/knowledge-bases/{knowledge_base_id}/evaluation-datasets",
    )
    client = TestClient(create_app())

    for path in paths:
        assert client.get(path).status_code == 401, path
    assert (
        client.post(
            f"/knowledge-bases/{knowledge_base_id}/rag/answer",
            json={"query": "How does it work?"},
        ).status_code
        == 401
    )
