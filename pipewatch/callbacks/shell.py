"""Shell callbacks: tab → URL sync and the shared DAG selection."""

from __future__ import annotations

from urllib.parse import quote

from dash import Input, Output, no_update
from flask import session as flask_session

from ..ui.shell import TAB_ROUTES

VALID_TABS = tuple(TAB_ROUTES)


def register(app) -> None:
    @app.callback(
        Output("url", "pathname"),
        Input("tabs", "value"),
        prevent_initial_call=True,
    )
    def tab_to_route(tab_value):
        tab = tab_value if tab_value in VALID_TABS else "timeline"
        flask_session["route_tab"] = tab
        return TAB_ROUTES[tab]

    @app.callback(
        Output("selected-dag", "data"),
        Output("url", "search"),
        Input("dag-picker", "value"),
        prevent_initial_call=True,
    )
    def dag_changed(dag_id):
        if not dag_id:
            return no_update, no_update
        flask_session["selected_dag"] = dag_id
        return dag_id, f"?dag={quote(str(dag_id), safe='')}"
