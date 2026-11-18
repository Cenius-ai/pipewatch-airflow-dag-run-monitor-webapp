"""Authentication endpoints: sign in, sign out, session probe."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .. import auth

bp = Blueprint("api_auth", __name__, url_prefix="/api")


def _payload() -> dict:
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        return body
    return request.form.to_dict()


@bp.post("/login")
def login():
    data = _payload()
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")

    if not username:
        return jsonify(
            {"error": "validation_error", "field": "username", "message": "Username is required"}
        ), 400
    if not password:
        return jsonify(
            {"error": "validation_error", "field": "password", "message": "Password is required"}
        ), 400

    if auth.login_rate_limited(request.remote_addr or "unknown"):
        return jsonify(
            {"error": "rate_limited", "message": "Too many sign-in attempts. Try again shortly."}
        ), 429, {"Retry-After": "60"}

    user = auth.authenticate(username, password)
    if user is None:
        return jsonify(
            {"error": "invalid_credentials", "message": "Invalid username or password"}
        ), 401

    auth.start_session(user)
    return jsonify(
        {
            "ok": True,
            "user": {
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
            },
        }
    )


@bp.post("/logout")
def logout():
    auth.end_session()
    return jsonify({"ok": True})


@bp.get("/session")
def session_probe():
    user = auth.current_user()
    if user is None:
        return jsonify({"authenticated": False, "user": None})
    return jsonify(
        {
            "authenticated": True,
            "user": {
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
            },
        }
    )
