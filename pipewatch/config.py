"""Runtime configuration for Pipewatch.

Every setting has a working default so a fresh clone boots with no .env file:
`python3 app.py` on a clean checkout must serve a populated dashboard.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Clearly-marked development fallback. `install.sh` writes a random SECRET_KEY
# into .env on a fresh checkout; without one the app still boots and the demo
# session works (the delivered artifact ships no .env).
DEV_SECRET_KEY = "cenius-dev-6a1f4d2b9c07e583"

SESSION_LIFETIME_HOURS = 12
LOGIN_ATTEMPT_LIMIT = 10
LOGIN_ATTEMPT_WINDOW_SECONDS = 60


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a local .env file when one is present."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(PROJECT_ROOT / ".env")


def database_url() -> str:
    """SQLite file at the project root unless DATABASE_URL says otherwise."""
    configured = os.environ.get("DATABASE_URL", "").strip()
    if configured:
        return configured
    return f"sqlite:///{PROJECT_ROOT / 'pipewatch.db'}"


def secret_key() -> str:
    return os.environ.get("SECRET_KEY") or DEV_SECRET_KEY
