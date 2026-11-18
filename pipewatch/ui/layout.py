"""Top-level Dash layout: sign-in card for anonymous, tabbed shell when signed in."""

from __future__ import annotations

from flask import session

from .. import auth
from ..services import queries
from . import log_panel as log_panel_module
from . import shell, signin

VALID_TABS = tuple(shell.TAB_ROUTES)


def _selected_dag_id(dags: list[dict]) -> str | None:
    wanted = session.get("selected_dag")
    known = [dag["dag_id"] for dag in dags]
    if wanted in known:
        return wanted
    return known[0] if known else None


def serve_layout():
    user = auth.current_user()
    if user is None:
        return signin.layout(next_path=session.get("login_next"))

    dags = queries.list_dags()
    selected_dag = _selected_dag_id(dags)
    active_tab = session.get("route_tab")
    if active_tab not in VALID_TABS:
        active_tab = "timeline"
    owner_value = session.get("owner_filter") or shell.OWNER_ALL

    log_panel = None
    log_run = session.get("log_run")
    if log_run and selected_dag:
        payload = queries.failed_tasks(selected_dag, log_run)
        log_panel = log_panel_module.log_panel(
            selected_dag,
            payload,
            close_href=log_panel_module.close_href_for(selected_dag, log_run),
        )

    return shell.layout(
        user=user,
        dags=dags,
        selected_dag=selected_dag,
        active_tab=active_tab,
        owner_value=owner_value,
        owners=queries.list_owners(),
        csrf_token_value=auth.csrf_token(),
        log_panel=log_panel,
    )
