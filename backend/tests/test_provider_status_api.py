"""Only authenticated metadata is available; no provider URLs, keys or probes."""

from fastapi.testclient import TestClient

from spurel.main import create_app
from spurel.security import require_api_token


def test_provider_status_is_protected(monkeypatch) -> None:
    monkeypatch.setenv("SPUREL_API_TOKEN", "a" * 48)
    response = TestClient(create_app()).get("/providers/status")
    assert response.status_code == 401


def test_provider_status_exposes_only_validated_model_metadata(monkeypatch) -> None:
    monkeypatch.setenv("SPUREL_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("SPUREL_GENERATION_PROVIDER", "openai_compatible")
    monkeypatch.setenv("SPUREL_OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", "nomic-embed-text")
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", "768")
    monkeypatch.setenv("SPUREL_GENERATION_MODEL", "hosted-chat")
    monkeypatch.setenv("SPUREL_GENERATION_BASE_URL", "https://api.example/v1")
    monkeypatch.setenv("SPUREL_GENERATION_API_KEY", "test-secret")
    app = create_app()
    app.dependency_overrides[require_api_token] = lambda: None
    response = TestClient(app).get("/providers/status")
    assert response.status_code == 200
    assert response.json() == {
        "embedding": {
            "provider": "ollama", "model": "nomic-embed-text",
            "configured": True, "dimensions": 768,
        },
        "generation": {
            "provider": "openai_compatible", "model": "hosted-chat",
            "configured": True, "dimensions": None,
        },
    }
    assert "test-secret" not in response.text
    assert "https://api.example" not in response.text
    assert "localhost:11434" not in response.text


def test_provider_status_reports_missing_secrets_without_echoing_them(monkeypatch) -> None:
    monkeypatch.setenv("SPUREL_EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("SPUREL_EMBEDDING_BASE_URL", "https://example/v1")
    monkeypatch.delenv("SPUREL_EMBEDDING_API_KEY", raising=False)
    monkeypatch.setenv("SPUREL_EMBEDDING_MODEL", "example")
    monkeypatch.setenv("SPUREL_EMBEDDING_DIMENSIONS", "2")
    monkeypatch.setenv("SPUREL_GENERATION_PROVIDER", "invalid")
    app = create_app()
    app.dependency_overrides[require_api_token] = lambda: None
    body = TestClient(app).get("/providers/status").json()
    assert body["embedding"]["configured"] is False
    assert body["generation"]["provider"] == "invalid"
    assert body["generation"]["configured"] is False
