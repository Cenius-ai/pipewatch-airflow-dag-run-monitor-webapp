"""Reusable UI atoms shared by every Pipewatch screen."""

from __future__ import annotations

from typing import Any

from dash import dcc, html

from .theme import format_duration


def state_badge(state: str) -> html.Span:
    label = (state or "unknown").replace("_", " ")
    return html.Span(
        [html.Span(className="badge-dot"), html.Span(label, className="badge-label")],
        className=f"badge badge--{state or 'unknown'}",
    )


def flag_metric(label: str, value: str, context: str | None = None, tone: str = "") -> html.Div:
    """Signature detail: a 1px leader line up to a 10px uppercase label chip."""
    children: list[Any] = [
        html.Div(
            [html.Span(className="metric-leader"), html.Span(label, className="metric-flag")],
            className="metric-flag-row",
        ),
        html.Div(value, className="metric-value"),
    ]
    if context:
        children.append(html.Div(context, className="metric-context"))
    return html.Div(children, className=f"metric {tone}".strip())


def metric_row(metrics: list[html.Div]) -> html.Div:
    return html.Div(metrics, className="metric-row")


def panel_header(title: str, subtitle: str, right: Any = None) -> html.Div:
    return html.Div(
        [
            html.Div([html.H2(title), html.P(subtitle, className="panel-subtitle")]),
            html.Div(right, className="panel-actions") if right else None,
        ],
        className="panel-header",
    )


def alert(message: str, tab: str, retry_visible: bool) -> html.Div:
    """Inline error alert + the retry control (always mounted, hidden when idle)."""
    if message:
        body = [html.Span("!", className="alert-mark", **{"aria-hidden": "true"}), message]
        alert_class = "alert alert--error"
    else:
        body = None
        alert_class = "alert alert--error alert--idle"
    return html.Div(
        [
            html.Div(
                body,
                id={"type": "panel-alert", "tab": tab},
                className=alert_class,
                role="alert",
            ),
            html.Button(
                "Retry",
                id={"type": "panel-retry", "tab": tab},
                n_clicks=0,
                className="btn btn--ghost",
                hidden=not retry_visible,
            ),
        ],
        className="alert-row",
    )


def silent_alert(tab: str) -> html.Div:
    """Idle placeholder so the retry control exists in every panel state."""
    return alert("", tab, retry_visible=False)


def empty_state(title: str, detail: str, action: Any = None) -> html.Div:
    return html.Div(
        [
            html.P(title, className="empty-title"),
            html.P(detail, className="empty-detail"),
            action,
        ],
        className="empty-state",
    )


def chart(figure, graph_id: str | None = None, height: int | None = None) -> dcc.Graph:
    kwargs: dict[str, Any] = {
        "figure": figure,
        "config": {"displayModeBar": False, "responsive": True},
        "className": "chart",
    }
    if graph_id:
        kwargs["id"] = graph_id
    if height:
        kwargs["style"] = {"height": f"{height}px"}
    return dcc.Graph(**kwargs)


def table(head: list[str], body: list[Any], caption: str, numeric_from: int = 1) -> html.Div:
    """Dense data table inside a horizontally scrollable container."""
    header_cells = []
    for index, label in enumerate(head):
        align = "num" if index >= numeric_from and label not in ("Log",) else ""
        header_cells.append(html.Th(label, scope="col", className=f"th {align}".strip()))
    return html.Div(
        html.Table(
            [
                html.Caption(caption, className="sr-only"),
                html.Thead(html.Tr(header_cells)),
                html.Tbody(body),
            ],
            className="data-table",
        ),
        className="table-scroll",
        role="region",
        **{"aria-label": caption, "tabIndex": 0},
    )


def duration_cell(seconds: float | int | None, tone: str = "") -> html.Td:
    return html.Td(format_duration(seconds), className=f"td num mono {tone}".strip())


def muted_dash() -> html.Td:
    return html.Td("—", className="td num muted")


def dag_context(dag: dict[str, Any] | None) -> html.Div:
    """Sticky filter-bar context line for the selected DAG."""
    if not dag:
        return html.Div("No DAG selected", className="dag-context")
    runs = dag.get("run_count", 0)
    return html.Div(
        [
            html.Span(dag["dag_id"], className="dag-context-id mono"),
            html.Span("·", className="dag-context-sep"),
            html.Span(f"owner {dag['owner']}"),
            html.Span("·", className="dag-context-sep"),
            html.Span(dag["schedule_interval"]),
            html.Span("·", className="dag-context-sep"),
            html.Span(f"SLA {dag['sla_minutes']}m"),
            html.Span("·", className="dag-context-sep"),
            html.Span(f"{runs} runs stored"),
        ],
        className="dag-context",
    )


__all__ = [
    "alert",
    "chart",
    "dag_context",
    "duration_cell",
    "empty_state",
    "flag_metric",
    "metric_row",
    "muted_dash",
    "panel_header",
    "silent_alert",
    "state_badge",
    "table",
]
