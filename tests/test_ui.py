"""Screens and Dash wiring: sign-in card, three-tab shell, panels, log view."""

from __future__ import annotations

from flask import session as flask_session

from tests.conftest import DEMO_PASSWORD, DEMO_USERNAME

TEXT_PROPS = ("children", "label", "value", "title", "data", "figure")


def _props(node) -> dict | None:
    if hasattr(node, "to_plotly_json"):
        return node.to_plotly_json().get("props", {})
    if isinstance(node, dict):
        return node.get("props", node)
    return None


def collect_text(node) -> str:
    """Flatten every string rendered by a Dash component tree."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, (int, float)):
        return str(node)
    if isinstance(node, (list, tuple)):
        return " ".join(collect_text(item) for item in node)
    props = _props(node)
    if props is None:
        return ""
    chunks = []
    for key in TEXT_PROPS:
        if key not in props:
            continue
        value = props[key]
        chunks.append(str(value) if key == "figure" else collect_text(value))
    return " ".join(chunk for chunk in chunks if chunk)


def find_component(node, component_id):
    """Depth-first lookup of a component by id (works on components and JSON)."""
    if isinstance(node, (list, tuple)):
        for item in node:
            found = find_component(item, component_id)
            if found is not None:
                return found
        return None
    props = _props(node)
    if props is None:
        return None
    if props.get("id") == component_id:
        return node
    return find_component(props.get("children"), component_id)


def test_public_pages_respond(client):
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_data(as_text=True) == "ok"


def test_dashboard_redirects_anonymous_users(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_anonymous_layout_is_the_sign_in_card(client):
    layout = client.get("/_dash-layout").get_json()
    text = collect_text(layout)
    assert "Sign in" in text
    assert "Demo: cenius@cenius.ai / cenius" in text
    assert find_component(layout, "login-username") is not None
    assert find_component(layout, "login-password") is not None
    assert find_component(layout, "login-submit") is not None
    # The sign-in card must carry dcc.Location so a successful login can navigate.
    assert find_component(layout, "url") is not None


def test_signed_in_layout_has_three_tabs_and_shared_picker(signed_in_client):
    layout = signed_in_client.get("/_dash-layout").get_json()
    text = collect_text(layout)
    for label in ("Run timeline", "Slowest tasks", "SLA misses"):
        assert label in text
    assert "Cenius Operator" in text
    assert find_component(layout, "dag-picker") is not None
    assert find_component(layout, "tabs") is not None
    assert find_component(layout, "panel") is not None
    tabs = find_component(layout, "tabs")
    assert len(_props(tabs)["children"]) == 3


def test_tab_routes_select_the_matching_tab(signed_in_client):
    for path, expected in (
        ("/dashboard", "timeline"),
        ("/dashboard/tasks", "tasks"),
        ("/dashboard/sla", "sla"),
    ):
        assert signed_in_client.get(path).status_code == 200
        layout = signed_in_client.get("/_dash-layout").get_json()
        assert _props(find_component(layout, "tabs"))["value"] == expected


def test_dag_query_parameter_persists_selection(signed_in_client):
    signed_in_client.get("/dashboard?dag=warehouse_sync_nightly")
    layout = signed_in_client.get("/_dash-layout").get_json()
    assert _props(find_component(layout, "dag-picker"))["value"] == "warehouse_sync_nightly"
    store = find_component(layout, "selected-dag")
    assert _props(store)["data"] == "warehouse_sync_nightly"


def test_panel_callback_renders_every_tab(callback, flask_server):
    render = callback("panel.children", "owner-filter-wrap.hidden")
    with flask_server.test_request_context("/"):
        flask_session["user_id"] = 1

        timeline, owner_hidden = render("timeline", "load_events_daily", "all", [], None)
        text = collect_text(timeline)
        assert "Run timeline" in text
        assert "load_events_daily" in text
        assert "success" in text and "failed" in text
        assert owner_hidden is True

        tasks, _ = render("tasks", "load_events_daily", "all", [], None)
        tasks_text = collect_text(tasks)
        assert "Slowest tasks" in tasks_text
        assert "p95" in tasks_text
        assert "last 30 runs" in tasks_text

        sla, owner_hidden = render("sla", None, "all", [], None)
        sla_text = collect_text(sla)
        assert "SLA misses" in sla_text
        assert "alice.chen" in sla_text
        assert owner_hidden is False


def test_panel_callback_filters_sla_by_owner(callback, flask_server):
    render = callback("panel.children", "owner-filter-wrap.hidden")
    with flask_server.test_request_context("/"):
        flask_session["user_id"] = 1
        panel, _ = render("sla", None, "marcus.oduya", [], None)
        text = collect_text(panel)
        assert "marcus.oduya" in text
        assert "alice.chen" not in text

        empty_panel, _ = render("sla", None, "nobody", [], None)
        empty_text = collect_text(empty_panel)
        assert "No SLA misses for nobody" in empty_text


def test_panel_callback_survives_unknown_dag_and_retry_clicks(callback, flask_server):
    render = callback("panel.children", "owner-filter-wrap.hidden")
    with flask_server.test_request_context("/"):
        flask_session["user_id"] = 1
        panel, _ = render("timeline", "missing-dag", "all", [1, None], None)
        assert "No runs recorded" in collect_text(panel) or "No DAGs available" in collect_text(panel)
        tasks, _ = render("tasks", "missing-dag", "all", [], None)
        assert collect_text(tasks)


def test_panel_callback_reports_missing_session(callback, flask_server):
    render = callback("panel.children", "owner-filter-wrap.hidden")
    with flask_server.test_request_context("/"):
        panel, hidden = render("timeline", "load_events_daily", "all", [], None)
        assert "Your session expired" in collect_text(panel)
        assert hidden is True


def test_log_view_renders_the_failed_task_excerpt(signed_in_client):
    runs = signed_in_client.get("/api/dags/load_events_daily/runs").get_json()["runs"]
    failed_run = next(run for run in runs if run["failed_task_count"] > 0)
    page = signed_in_client.get(
        f"/dashboard/logs?dag=load_events_daily&run={failed_run['run_id']}"
    )
    assert page.status_code == 200
    layout = signed_in_client.get("/_dash-layout").get_json()
    text = collect_text(layout)
    assert "Failed task logs" in text
    assert "showing last" in text
    assert "log-line--error" in str(layout)
    assert failed_run["run_id"] in text


def test_log_view_close_link_keeps_the_run_selected(signed_in_client):
    runs = signed_in_client.get("/api/dags/load_events_daily/runs").get_json()["runs"]
    failed_run = next(run for run in runs if run["failed_task_count"] > 0)
    signed_in_client.get(
        f"/dashboard/logs?dag=load_events_daily&run={failed_run['run_id']}"
    )
    layout = signed_in_client.get("/_dash-layout").get_json()
    assert f"/dashboard?dag=load_events_daily&run={failed_run['run_id']}" in str(layout)


def test_tab_url_sync_callback(callback, flask_server):
    sync = callback("url.pathname")
    with flask_server.test_request_context("/"):
        assert sync("tasks") == "/dashboard/tasks"
        assert sync("sla") == "/dashboard/sla"
        assert sync("timeline") == "/dashboard"
        assert flask_session["route_tab"] == "timeline"


def test_dag_change_callback_mirrors_url(callback, flask_server):
    change = callback("selected-dag.data", "url.search")
    with flask_server.test_request_context("/"):
        dag_id, search = change("publish_metrics_daily")
        assert dag_id == "publish_metrics_daily"
        assert search == "?dag=publish_metrics_daily"
        assert flask_session["selected_dag"] == "publish_metrics_daily"


def test_security_headers_are_present(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_local_assets_are_served(client):
    index = client.get("/").get_data(as_text=True)
    assert "/assets/style.css" in index
    assert "assets/favicon.svg" in index
    assert 'lang="en"' in index
    for path, content_type in (
        ("/assets/style.css", "text/css"),
        ("/assets/fonts.css", "text/css"),
        ("/assets/favicon.svg", "image/svg"),
        ("/assets/fonts/lexend-var-latin.woff2", "font/woff2"),
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert content_type in response.headers["Content-Type"]


def test_logout_form_is_rendered_with_a_csrf_token(signed_in_client):
    layout = signed_in_client.get("/_dash-layout").get_json()
    text = str(layout)
    assert 'action="/logout"' in text.replace("'", '"') or "/logout" in text
    assert "csrf_token" in text


def test_logout_post_clears_the_session(signed_in_client):
    layout = signed_in_client.get("/_dash-layout").get_json()
    token = _props(find_component(layout, "logout-csrf"))["value"]
    assert token and len(token) >= 20, "the sign-out form must carry a CSRF token"
    response = signed_in_client.post("/logout", data={"csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert signed_in_client.get("/api/dags").status_code == 401


def test_demo_credentials_are_stated_on_the_signin_card(client):
    layout = client.get("/_dash-layout").get_json()
    text = collect_text(layout)
    assert f"{DEMO_USERNAME}" in text
    assert DEMO_PASSWORD in text
