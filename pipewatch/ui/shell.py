"""Signed-in shell: top bar with dcc.Tabs, sticky filter bar, content, footer."""

from __future__ import annotations

from typing import Any

from dash import dcc, html

from ..ui import components
from ..ui.signin import brand_mark
from .theme import PRODUCT_NAME, PRODUCT_TAGLINE

TAB_ROUTES = {
    "timeline": "/dashboard",
    "tasks": "/dashboard/tasks",
    "sla": "/dashboard/sla",
}
TAB_LABELS = {
    "timeline": "Run timeline",
    "tasks": "Slowest tasks",
    "sla": "SLA misses",
}
OWNER_ALL = "all"


def top_bar(user: dict[str, Any], active_tab: str, csrf_token_value: str) -> html.Header:
    tabs = dcc.Tabs(
        id="tabs",
        value=active_tab,
        children=[
            dcc.Tab(
                label=TAB_LABELS[key],
                value=key,
                className="topnav-tab",
                selected_className="topnav-tab--selected",
            )
            for key in ("timeline", "tasks", "sla")
        ],
        parent_className="topnav",
        className="topnav-tabs",
        content_className="topnav-content",
    )
    return html.Header(
        [
            html.Div(
                [
                    brand_mark(),
                    html.Div(
                        [
                            html.Span(PRODUCT_NAME, className="brand-name"),
                            html.Span(PRODUCT_TAGLINE, className="brand-sub"),
                        ],
                        className="brand-text",
                    ),
                ],
                className="brand",
            ),
            html.Nav(tabs, className="primary-nav", **{"aria-label": "Dashboard views"}),
            html.Div(
                [
                    html.Span(
                        [
                            html.Span(user["display_name"], className="user-name"),
                            html.Span(user["role"], className="user-role"),
                        ],
                        className="user-chip",
                    ),
                    html.Form(
                        [
                            dcc.Input(id="logout-csrf", type="hidden", name="csrf_token", value=csrf_token_value),
                            html.Button(
                                "Sign out",
                                type="submit",
                                className="btn btn--ghost btn--sm",
                            ),
                        ],
                        method="post",
                        action="/logout",
                        className="signout-form",
                    ),
                ],
                className="topbar-right",
            ),
        ],
        className="topbar",
    )


def filter_bar(
    dags: list[dict[str, Any]],
    selected_dag: str | None,
    owners: list[str],
    owner_value: str,
) -> html.Div:
    dag = next((item for item in dags if item["dag_id"] == selected_dag), None)
    dag_options = [
        {"label": f"{item['dag_id']} · {item['owner']}", "value": item["dag_id"]} for item in dags
    ]
    owner_options = [{"label": "All owners", "value": OWNER_ALL}] + [
        {"label": owner, "value": owner} for owner in owners
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Label("DAG", htmlFor="dag-picker", className="sr-only"),
                    dcc.Dropdown(
                        id="dag-picker",
                        options=dag_options,
                        value=selected_dag,
                        clearable=False,
                        searchable=True,
                        className="dag-picker",
                        optionHeight=38,
                    ),
                    components.dag_context(dag),
                ],
                className="filter-group",
            ),
            html.Div(
                [
                    html.Label("Owner", htmlFor="owner-filter", className="sr-only"),
                    dcc.Dropdown(
                        id="owner-filter",
                        options=owner_options,
                        value=owner_value,
                        clearable=False,
                        searchable=False,
                        className="owner-picker",
                    ),
                ],
                id="owner-filter-wrap",
                className="filter-group filter-group--owner",
                hidden=True,
            ),
        ],
        className="filterbar",
    )


def footer() -> html.Footer:
    links = [("Run timeline", "/dashboard"), ("Slowest tasks", "/dashboard/tasks"), ("SLA misses", "/dashboard/sla")]
    return html.Footer(
        [
            html.Nav(
                [html.A(label, href=href, className="footer-link") for label, href in links],
                className="footer-nav",
                **{"aria-label": "Dashboard views"},
            ),
            html.P(
                "Read-only demo data · seeded SQLite mirror · no Airflow connection",
                className="footer-note",
            ),
        ],
        className="app-footer",
    )


def layout(
    user: dict[str, Any],
    dags: list[dict[str, Any]],
    selected_dag: str | None,
    active_tab: str,
    owner_value: str,
    owners: list[str],
    csrf_token_value: str,
    log_panel: Any = None,
) -> html.Div:
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="selected-dag", data=selected_dag),
            dcc.Store(id="selected-run", data=None),
            top_bar(user, active_tab, csrf_token_value),
            filter_bar(dags, selected_dag, owners, owner_value),
            html.Main(
                [
                    html.H1(
                        f"{PRODUCT_NAME} — {PRODUCT_TAGLINE}",
                        className="sr-only",
                    ),
                    dcc.Loading(
                        html.Div(id="panel", className="panel-host"),
                        type="circle",
                        color="#ed7940",
                        className="panel-loading",
                    ),
                    log_panel,
                ],
                className="content",
            ),
            footer(),
        ],
        className="page page--app",
    )
