"""Test fixtures: a throwaway SQLite file seeded through the normal boot path."""

from __future__ import annotations

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="pipewatch-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/pipewatch-test.db"
os.environ["SECRET_KEY"] = "pipewatch-test-session-key"

import pytest  # noqa: E402

import app as app_module  # noqa: E402  (imports seed the temp database)
from pipewatch import config as pipewatch_config  # noqa: E402

# The limiter is exercised explicitly; keep unrelated logins from tripping it.
pipewatch_config.LOGIN_ATTEMPT_LIMIT = 10_000

DEMO_USERNAME = "cenius"
DEMO_EMAIL = "cenius@cenius.ai"
DEMO_PASSWORD = "cenius"


@pytest.fixture(scope="session")
def flask_server():
    return app_module.server


@pytest.fixture(scope="session")
def dash_app():
    return app_module.app


@pytest.fixture()
def client(flask_server):
    with flask_server.test_client() as test_client:
        yield test_client


@pytest.fixture()
def signed_in_client(client):
    response = client.post(
        "/api/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return client


@pytest.fixture()
def callback(flask_server, dash_app):
    """Resolve a registered Dash callback function by its output ids."""

    def _resolve(*output_markers):
        for key, spec in dash_app.callback_map.items():
            if all(marker in key for marker in output_markers):
                return getattr(spec["callback"], "__wrapped__", spec["callback"])
        raise AssertionError(f"no callback with outputs {output_markers}")

    return _resolve
