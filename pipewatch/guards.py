"""Shared request guards: one gate for every /api data route."""

from __future__ import annotations

from flask import jsonify, request

from . import auth

PUBLIC_API_PATHS = frozenset({"/api/session", "/api/login"})


def register_guards(server) -> None:
    @server.before_request
    def require_session_for_api():
        """401 JSON for every guarded data route when the session is anonymous."""
        path = request.path.rstrip("/") or "/"
        if not path.startswith("/api/"):
            return None
        if path in PUBLIC_API_PATHS:
            return None
        if auth.current_user() is None:
            return jsonify({"error": "authentication required"}), 401
        return None
