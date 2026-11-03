"""Initialize local Compose configuration without printing or overwriting secrets."""

import os
import re
import secrets
import sys
import tempfile
from pathlib import Path

_TOKEN_LINE = re.compile(r"(?m)^SPUREL_API_TOKEN=(.*)$")
_MIN_TOKEN_LENGTH = 32


def initialize_env(root: Path) -> None:
    """Create an ignored local .env with a strong API token, idempotently."""
    target = root / ".env"
    example = root / ".env.example"
    if target.is_symlink():
        raise ValueError("Refusing to modify an .env symlink")

    existed = target.exists()
    content = target.read_text(encoding="utf-8") if existed else example.read_text(
        encoding="utf-8"
    )
    matches = list(_TOKEN_LINE.finditer(content))
    if len(matches) != 1:
        raise ValueError("Exactly one SPUREL_API_TOKEN setting is required")

    match = matches[0]
    token = match.group(1)
    if not token:
        token = secrets.token_urlsafe(48)
        content = content[:match.start(1)] + token + content[match.end(1):]
    elif (
        len(token) < _MIN_TOKEN_LENGTH
        or not token.isascii()
        or not token.isprintable()
        or any(character.isspace() for character in token)
    ):
        raise ValueError("SPUREL_API_TOKEN must be at least 32 printable ASCII characters")

    if not existed or target.read_text(encoding="utf-8") != content:
        # Atomic replacement avoids leaving half-written secrets after a crash.
        descriptor, temporary = tempfile.mkstemp(prefix=".spurel-env-", dir=root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    os.chmod(target, 0o600)


if __name__ == "__main__":
    try:
        initialize_env(Path(__file__).resolve().parents[1])
    except (OSError, ValueError) as error:
        print(f"Local environment setup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print("Local .env is ready (API token is not displayed).")
