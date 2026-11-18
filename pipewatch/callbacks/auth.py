"""Sign-in callbacks: validation, busy state, single credential error."""

from __future__ import annotations

from dash import Input, Output, State, no_update
from flask import request

from .. import auth

DEFAULT_SUCCESS_ROUTE = "/dashboard"


def _client_key() -> str:
    return request.remote_addr or "unknown"


def register(app) -> None:
    triggers = dict(
        inputs=[
            Input("login-submit", "n_clicks"),
            Input("login-password", "n_submit"),
            Input("login-username", "n_submit"),
        ],
        prevent_initial_call=True,
    )

    @app.callback(
        Output("login-user-error", "children"),
        Output("login-pass-error", "children"),
        Output("login-alert", "children"),
        Output("url", "href"),
        Output("login-attempt", "data"),
        *triggers["inputs"],
        State("login-username", "value"),
        State("login-password", "value"),
        State("login-csrf", "value"),
        State("login-attempt", "data"),
        prevent_initial_call=True,
    )
    def submit_signin(_clicks, _password_enter, _username_enter, username, password, csrf, attempt):
        attempt = int(attempt or 0) + 1
        typed_user = username or ""
        username_error = "" if typed_user.strip() else "Username is required"
        password_error = "" if password else "Password is required"
        if username_error or password_error:
            return username_error, password_error, "", no_update, attempt

        if not auth.csrf_valid(csrf):
            return "", "", "Your sign-in session expired. Reload the page and try again.", no_update, attempt

        if auth.login_rate_limited(_client_key()):
            return "", "", "Too many sign-in attempts. Wait a minute and try again.", no_update, attempt

        user = auth.authenticate(typed_user, password)
        if user is None:
            return "", "", "Invalid username or password", no_update, attempt

        auth.start_session(user)
        return "", "", "", DEFAULT_SUCCESS_ROUTE, attempt

    @app.callback(
        Output("login-submit", "children"),
        Output("login-submit", "disabled"),
        *triggers["inputs"],
        prevent_initial_call=True,
    )
    def show_busy_state(_clicks, _password_enter, _username_enter):
        return "Signing in…", True

    @app.callback(
        Output("login-submit", "children", allow_duplicate=True),
        Output("login-submit", "disabled", allow_duplicate=True),
        Input("login-attempt", "data"),
        prevent_initial_call=True,
    )
    def reset_submit_state(_attempt):
        # Runs only after the credential check finished (failed sign-ins keep the form usable).
        return "Sign in", False

    @app.callback(
        Output("login-password", "type"),
        Output("login-toggle", "children"),
        Input("login-toggle", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_password(clicks):
        if int(clicks or 0) % 2 == 1:
            return "text", "Hide"
        return "password", "Show"
