"""Flask wiring around the Dash app: auth gates, index serving, headers."""

from __future__ import annotations

import secrets
from datetime import timedelta
from urllib.parse import quote

from flask import jsonify, redirect, request, session
from werkzeug.exceptions import HTTPException

from . import auth, config
from .guards import register_guards
from .routes import api_auth, api_data
from .services import queries

# A fresh nonce is minted per response and stamped onto every inline <script> in
# the HTML we serve (Dash ships one renderer bootstrap script), so the policy can
# stay free of 'unsafe-inline' while still executing our own page scripts.
CSP_TEMPLATE = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)

def _safe_next(candidate: str | None) -> str | None:
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return None
    return candidate


def create_server(server, dash_app) -> None:
    server.config.update(
        SECRET_KEY=config.secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # the demo is served over plain http
        SESSION_COOKIE_NAME="pipewatch_session",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=config.SESSION_LIFETIME_HOURS),
        JSON_SORT_KEYS=False,
        TRAP_HTTP_EXCEPTIONS=False,
    )

    register_guards(server)
    server.register_blueprint(api_auth.bp)
    server.register_blueprint(api_data.bp)

    @server.after_request
    def apply_security_headers(response):
        nonce = secrets.token_urlsafe(16)
        if response.mimetype == "text/html":
            body = response.get_data(as_text=True)
            if "<script" in body:
                response.set_data(body.replace("<script", f'<script nonce="{nonce}"'))
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy", CSP_TEMPLATE.format(nonce=nonce)
        )
        return response

    @server.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    {
                        "error": (error.name or "error").lower().replace(" ", "_"),
                        "message": error.description,
                    }
                ),
                error.code or 500,
            )
        return error

    @server.get("/health")
    def health():
        return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @server.get("/login")
    def login_page():
        if auth.current_user() is not None:
            return redirect("/dashboard")
        session["login_next"] = _safe_next(request.args.get("next"))
        return dash_app.index()

    def _guard_dashboard(tab: str, open_logs: bool = False):
        if auth.current_user() is None:
            target = request.full_path.rstrip("?")
            return redirect("/login?next=" + quote(target, safe="/"))
        session["route_tab"] = tab
        dag_id = request.args.get("dag")
        if dag_id and queries.dag_exists(dag_id):
            session["selected_dag"] = dag_id
        run_id = request.args.get("run") or None
        session["selected_run"] = run_id
        session["log_run"] = run_id if open_logs else None
        return dash_app.index()

    @server.get("/dashboard")
    def dashboard_timeline():
        return _guard_dashboard("timeline")

    @server.get("/dashboard/tasks")
    def dashboard_tasks():
        return _guard_dashboard("tasks")

    @server.get("/dashboard/sla")
    def dashboard_sla():
        return _guard_dashboard("sla")

    @server.get("/dashboard/logs")
    def dashboard_logs():
        return _guard_dashboard("timeline", open_logs=True)

    @server.post("/logout")
    def logout():
        if not auth.csrf_valid(request.form.get("csrf_token")):
            return redirect("/dashboard")
        auth.end_session()
        return redirect("/login")
