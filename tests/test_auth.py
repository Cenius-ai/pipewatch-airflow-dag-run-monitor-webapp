"""Auth: the shared API guard, login/logout and the session cookie attributes."""

from __future__ import annotations

import pytest

from tests.conftest import DEMO_EMAIL, DEMO_PASSWORD, DEMO_USERNAME

GUARDED_PATHS = [
    "/api/dags",
    "/api/dags/load_events_daily/runs",
    "/api/dags/load_events_daily/task-stats",
    "/api/sla-misses",
    "/api/owners",
    "/api/dags/load_events_daily/runs/scheduled__2026-01-01T00:00:00/failed-tasks",
]


@pytest.mark.parametrize("path", GUARDED_PATHS)
def test_guard_rejects_anonymous_calls(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_session_probe_is_public(client):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.get_json() == {"authenticated": False, "user": None}


def test_login_success_sets_hardened_cookie(client):
    response = client.post(
        "/api/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["user"]["username"] == "cenius"
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie.replace(" ", "")
    assert "Secure" not in cookie


def test_login_accepts_email_identifier(client):
    response = client.post(
        "/api/login", json={"username": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == "cenius"


def test_login_error_is_non_enumerating(client):
    wrong_password = client.post(
        "/api/login", json={"username": DEMO_USERNAME, "password": "nope"}
    )
    unknown_user = client.post(
        "/api/login", json={"username": "ghost", "password": "nope"}
    )
    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert (
        wrong_password.get_json()["message"]
        == unknown_user.get_json()["message"]
        == "Invalid username or password"
    )


def test_login_field_validation(client):
    empty_username = client.post("/api/login", json={"username": "", "password": "x"})
    empty_password = client.post("/api/login", json={"username": "cenius", "password": ""})
    assert empty_username.status_code == 400
    assert empty_username.get_json()["field"] == "username"
    assert empty_password.status_code == 400
    assert empty_password.get_json()["field"] == "password"


def test_session_probe_after_login(signed_in_client):
    body = signed_in_client.get("/api/session").get_json()
    assert body["authenticated"] is True
    assert body["user"]["username"] == "cenius"
    assert body["user"]["display_name"] == "Cenius Operator"


def test_guard_opens_after_login(signed_in_client):
    response = signed_in_client.get("/api/dags")
    assert response.status_code == 200
    assert len(response.get_json()["dags"]) == 6


def test_logout_invalidates_the_session(signed_in_client):
    assert signed_in_client.post("/api/logout").status_code == 200
    assert signed_in_client.get("/api/dags").status_code == 401
    assert signed_in_client.get("/api/session").get_json()["authenticated"] is False


def test_session_cookie_configuration(flask_server):
    assert flask_server.config["SESSION_COOKIE_HTTPONLY"] is True
    assert flask_server.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert flask_server.config["SESSION_COOKIE_SECURE"] is False


def test_login_rate_limit(client, monkeypatch):
    from pipewatch import config as pipewatch_config

    monkeypatch.setattr(pipewatch_config, "LOGIN_ATTEMPT_LIMIT", 2)
    monkeypatch.setattr(pipewatch_config, "LOGIN_ATTEMPT_WINDOW_SECONDS", 60)
    from pipewatch import auth

    auth._attempts.clear()
    payload = {"username": DEMO_USERNAME, "password": "wrong"}
    statuses = [client.post("/api/login", json=payload).status_code for _ in range(4)]
    assert 429 in statuses
    auth._attempts.clear()
