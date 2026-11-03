"""Initialize local Compose configuration without printing or overwriting secrets."""

import os
import re
import secrets
import sys
import tempfile
from pathlib import Path

_SECRET_FIELDS = (
    "SPUREL_API_TOKEN",
    "SPUREL_FRONTEND_OPERATOR_PASSWORD",
    "SPUREL_FRONTEND_SESSION_SECRET",
)
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
    for field in _SECRET_FIELDS:
        expression = re.compile(rf"(?m)^{re.escape(field)}=(.*)$")
        matches = list(expression.finditer(content))
        if len(matches) > 1:
            raise ValueError(f"Exactly one {field} setting is required")

        if not matches:
            content = content.rstrip("\n") + f"\n{field}={secrets.token_urlsafe(48)}\n"
            continue

        match = matches[0]
        value = match.group(1)
        if not value:
            value = secrets.token_urlsafe(48)
            content = content[:match.start(1)] + value + content[match.end(1):]
        elif (
            len(value) < _MIN_TOKEN_LENGTH
            or len(value) > 512
            or not value.isascii()
            or not value.isprintable()
            or any(character.isspace() for character in value)
        ):
            raise ValueError(f"{field} must be 32-512 printable ASCII characters")

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
