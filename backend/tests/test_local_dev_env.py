"""Local development env bootstrap must be safe and repeatable."""

import os
import runpy
import stat
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "init_dev_env.py"
initialize_env = runpy.run_path(str(_SCRIPT))["initialize_env"]


def _template(root: Path) -> None:
    (root / ".env.example").write_text(
        "SPUREL_API_TOKEN=\nOPENAI_API_KEY=\nSPUREL_POSTGRES_PASSWORD=spurel\n",
        encoding="utf-8",
    )


def test_bootstrap_generates_strong_token_and_is_idempotent(tmp_path: Path) -> None:
    _template(tmp_path)
    initialize_env(tmp_path)

    content = (tmp_path / ".env").read_text(encoding="utf-8")
    token = next(
        line.removeprefix("SPUREL_API_TOKEN=")
        for line in content.splitlines()
        if line.startswith("SPUREL_API_TOKEN=")
    )
    assert len(token) >= 32
    assert token.isascii()
    assert token.isprintable()
    assert all(not character.isspace() for character in token)
    if os.name == "posix":
        assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600

    initialize_env(tmp_path)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == content


def test_bootstrap_does_not_overwrite_existing_secrets(tmp_path: Path) -> None:
    _template(tmp_path)
    original = (
        "SPUREL_API_TOKEN=" + "A" * 48 + "\n"
        "OPENAI_API_KEY=user-secret\n"
        "SPUREL_POSTGRES_PASSWORD=custom-local-password\n"
    )
    target = tmp_path / ".env"
    target.write_text(original, encoding="utf-8")

    initialize_env(tmp_path)

    updated = target.read_text(encoding="utf-8")
    assert updated.startswith(original)
    for field in ("SPUREL_FRONTEND_OPERATOR_PASSWORD", "SPUREL_FRONTEND_SESSION_SECRET"):
        values = [line.split("=", 1)[1] for line in updated.splitlines() if line.startswith(field + "=")]
        assert len(values) == 1 and len(values[0]) >= 32
    initialize_env(tmp_path)
    assert target.read_text(encoding="utf-8") == updated


@pytest.mark.parametrize(
    "token",
    ["short", "A" * 31, "A" * 32 + " ", "A" * 32 + "\t"],
)
def test_bootstrap_refuses_weak_or_whitespace_tokens(tmp_path: Path, token: str) -> None:
    _template(tmp_path)
    original = f"SPUREL_API_TOKEN={token}\nOPENAI_API_KEY=existing-secret\n"
    target = tmp_path / ".env"
    target.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="SPUREL_API_TOKEN"):
        initialize_env(tmp_path)

    assert target.read_text(encoding="utf-8") == original


def test_bootstrap_refuses_ambiguous_duplicate_token_settings(tmp_path: Path) -> None:
    _template(tmp_path)
    (tmp_path / ".env").write_text(
        "SPUREL_API_TOKEN=\nSPUREL_API_TOKEN=another\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Exactly one"):
        initialize_env(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX symlink semantics")
def test_bootstrap_refuses_symlink_target(tmp_path: Path) -> None:
    _template(tmp_path)
    external = tmp_path / "external-secrets"
    external.write_text("SPUREL_API_TOKEN=existing-secret\n", encoding="utf-8")
    (tmp_path / ".env").symlink_to(external)

    with pytest.raises(ValueError, match="symlink"):
        initialize_env(tmp_path)

    assert external.read_text(encoding="utf-8") == "SPUREL_API_TOKEN=existing-secret\n"


@pytest.mark.parametrize(
    "field",
    ["SPUREL_FRONTEND_OPERATOR_PASSWORD", "SPUREL_FRONTEND_SESSION_SECRET"],
)
def test_frontend_secrets_must_be_strong_and_unique(tmp_path: Path, field: str) -> None:
    _template(tmp_path)
    target = tmp_path / ".env"
    token = "X" * 48
    original = f"SPUREL_API_TOKEN={token}\n{field}=weak\n"
    target.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match=field):
        initialize_env(tmp_path)
    assert target.read_text(encoding="utf-8") == original


def test_frontend_secrets_are_distinct_from_api_token(tmp_path: Path) -> None:
    _template(tmp_path)
    initialize_env(tmp_path)
    config = dict(
        line.split("=", 1)
        for line in (tmp_path / ".env").read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
    )
    tokens = [
        config["SPUREL_API_TOKEN"],
        config["SPUREL_FRONTEND_OPERATOR_PASSWORD"],
        config["SPUREL_FRONTEND_SESSION_SECRET"],
    ]
    assert len(set(tokens)) == 3
    assert all(len(token) >= 32 for token in tokens)
