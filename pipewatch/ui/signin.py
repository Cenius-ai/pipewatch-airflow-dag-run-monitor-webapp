"""The sign-in screen (`/login`) rendered inside the Dash app."""

from __future__ import annotations

from dash import dcc, html

from .. import auth

DEMO_USERNAME = "cenius"
DEMO_EMAIL = "cenius@cenius.ai"
DEMO_PASSWORD = "cenius"


def brand_mark() -> html.Span:
    return html.Span(
        [
            html.Span(className="brand-ring"),
            html.Span(className="brand-dot"),
        ],
        className="brand-mark",
        **{"aria-hidden": "true"},
    )


def shell_placeholders() -> html.Div:
    """Keep every dashboard callback id resolvable while the sign-in card is shown.

    They are hidden and inert; they simply guarantee that no callback ever looks
    for a component that is not in the rendered layout.
    """
    return html.Div(
        [
            dcc.Store(id="selected-dag", data=None),
            dcc.Store(id="selected-run", data=None),
            dcc.Tabs(id="tabs", value="timeline", children=[], style={"display": "none"}),
            dcc.Dropdown(
                id="owner-filter", options=[], value=None, style={"display": "none"}
            ),
            html.Div(id="owner-filter-wrap", hidden=True),
            html.Div(id="panel", hidden=True),
        ],
        hidden=True,
        **{"aria-hidden": "true"},
    )


def layout(next_path: str | None = None) -> html.Div:
    """Centered sign-in card with inline validation, toggle and demo hint."""
    subtitle = "Sign in to open the run-health dashboard."
    if next_path and next_path not in ("/", "/login"):
        subtitle = f"Sign in to continue to {next_path}."

    return html.Div(
        [
            dcc.Location(id="url"),
            dcc.Store(id="login-attempt", data=0),
            shell_placeholders(),
            html.Main(
                html.Div(
                    [
                        html.Section(
                            [
                                html.Div(
                                    [brand_mark(), html.Span("Pipewatch", className="brand-name")],
                                    className="brand",
                                ),
                                html.P(
                                    "Airflow DAG Run Monitor",
                                    className="brand-kicker",
                                ),
                                html.H1(
                                    "See every DAG run, slow task and SLA miss without opening the Airflow UI.",
                                    className="signin-headline",
                                ),
                                html.Ul(
                                    [
                                        html.Li("Run timeline with success, failure and duration per run"),
                                        html.Li("Slowest tasks leaderboard with p50 / p95 durations"),
                                        html.Li("Failed-task log excerpts with the error line highlighted"),
                                        html.Li("SLA misses filtered by owner"),
                                    ],
                                    className="signin-points",
                                ),
                            ],
                            className="signin-intro",
                        ),
                        html.Section(
                            [
                                html.H2("Sign in", className="card-title"),
                                html.P(subtitle, className="card-subtitle"),
                                html.Div(
                                    [
                                        html.Label("Username", htmlFor="login-username", className="label"),
                                        dcc.Input(
                                            id="login-username",
                                            type="text",
                                            className="input",
                                            placeholder="cenius",
                                            autoComplete="username",
                                            n_submit=0,
                                            debounce=False,
                                        ),
                                        html.P(
                                            id="login-user-error",
                                            className="field-error",
                                            role="alert",
                                        ),
                                    ],
                                    className="field",
                                ),
                                html.Div(
                                    [
                                        html.Label("Password", htmlFor="login-password", className="label"),
                                        html.Div(
                                            [
                                                dcc.Input(
                                                    id="login-password",
                                                    type="password",
                                                    className="input",
                                                    placeholder="••••••",
                                                    autoComplete="current-password",
                                                    n_submit=0,
                                                    debounce=False,
                                                ),
                                                html.Button(
                                                    "Show",
                                                    id="login-toggle",
                                                    type="button",
                                                    className="input-toggle",
                                                    **{"aria-label": "Show or hide the password"},
                                                ),
                                            ],
                                            className="input-with-toggle",
                                        ),
                                        html.P(
                                            id="login-pass-error",
                                            className="field-error",
                                            role="alert",
                                        ),
                                    ],
                                    className="field",
                                ),
                                html.Div(id="login-alert", className="alert alert--error", role="alert"),
                                html.Button(
                                    "Sign in",
                                    id="login-submit",
                                    type="submit",
                                    className="btn btn--primary btn--block",
                                ),
                                dcc.Input(
                                    id="login-csrf",
                                    type="hidden",
                                    value=auth.csrf_token(),
                                ),
                                html.Div(
                                    [
                                        html.P(
                                            f"Demo: {DEMO_EMAIL} / {DEMO_PASSWORD}",
                                            className="demo-hint",
                                        ),
                                        html.P(
                                            "Second demo account: airflow / airflow-demo",
                                            className="demo-hint demo-hint--secondary",
                                        ),
                                    ],
                                    className="demo-hint-block",
                                ),
                            ],
                            className="signin-card",
                        ),
                    ],
                    className="signin-grid",
                ),
                className="signin-shell",
            ),
            html.Footer(
                html.P(
                    "Read-only demo data seeded into a local SQLite file — no Airflow connection required.",
                    className="footer-note",
                ),
                className="app-footer app-footer--signin",
            ),
        ],
        className="page page--signin",
    )
