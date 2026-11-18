"""Single callback that renders the selected tab's panel."""

from __future__ import annotations

import logging

from dash import ALL, Input, Output, State, html
from sqlalchemy.exc import SQLAlchemyError

from .. import auth
from ..services import queries
from ..ui import panels

logger = logging.getLogger("pipewatch.panel")

RUNS_ERROR = "Could not load runs"
STATS_ERROR = "Could not load task stats"
SLA_ERROR = "Could not load SLA misses"
SESSION_ERROR = "Your session expired. Reload the page and sign in again."

VALID_TABS = ("timeline", "tasks", "sla")


def _session_expired() -> html.Div:
    return html.Section(
        html.Div(
            [html.Span("!", className="alert-mark", **{"aria-hidden": "true"}), SESSION_ERROR],
            className="alert alert--error",
            role="alert",
        ),
        className="panel",
    )


def register(app) -> None:
    @app.callback(
        Output("panel", "children"),
        Output("owner-filter-wrap", "hidden"),
        Input("tabs", "value"),
        Input("selected-dag", "data"),
        Input("owner-filter", "value"),
        Input({"type": "panel-retry", "tab": ALL}, "n_clicks"),
        State("selected-run", "data"),
    )
    def render_panel(tab_value, dag_id, owner_value, _retries, selected_run):
        if auth.current_user() is None:
            return _session_expired(), True

        tab = tab_value if tab_value in VALID_TABS else "timeline"
        dag = queries.get_dag(dag_id) if dag_id else None
        owner = owner_value if owner_value else "all"

        if tab == "sla":
            try:
                payload = queries.sla_misses(owner=owner, limit=50)
            except SQLAlchemyError:
                logger.exception("failed loading SLA misses (owner=%s)", owner)
                return panels.sla_panel(None, owner, SLA_ERROR), False
            return panels.sla_panel(payload, owner, None), False

        if dag_id is None:
            if tab == "tasks":
                return panels.task_stats_panel(None, [], None), True
            return panels.timeline_panel(None, [], None, selected_run), True

        if tab == "tasks":
            try:
                stats = queries.task_stats(dag_id, window=queries.DEFAULT_STATS_WINDOW)
            except SQLAlchemyError:
                logger.exception("failed loading task stats (dag=%s)", dag_id)
                return panels.task_stats_panel(dag, [], STATS_ERROR), True
            return panels.task_stats_panel(dag, stats or [], None), True

        try:
            runs = queries.list_runs(dag_id, limit=queries.DEFAULT_RUN_LIMIT)
        except SQLAlchemyError:
            logger.exception("failed loading runs (dag=%s)", dag_id)
            return panels.timeline_panel(dag, [], RUNS_ERROR, selected_run), True
        return panels.timeline_panel(dag, runs or [], None, selected_run), True
