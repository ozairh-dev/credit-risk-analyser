"""Reads secrets that must never be hard-coded or committed (CLAUDE.md rule 6/7).

`.env` is not auto-loaded into the process environment (no python-dotenv in the
stack), so this parses it directly. A real environment variable always wins
over the file, matching normal dotenv convention.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def _read_env_file() -> dict:
    if not ENV_FILE.exists():
        return {}
    values = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def sec_user_agent() -> str:
    """The User-Agent SEC requires on every request (docs/data-sources.md)."""
    value = os.environ.get("SEC_USER_AGENT") or _read_env_file().get("SEC_USER_AGENT")
    if not value:
        raise RuntimeError(
            "SEC_USER_AGENT is not set. Copy .env.example to .env and add your "
            "real name and email — the SEC blocks requests without one."
        )
    return value
