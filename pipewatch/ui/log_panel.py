"""Failed-task log excerpt panel (the `/dashboard/logs` view)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from dash import html

from . import components
from .theme import format_datetime, format_duration

MAX_EXCERPT_LINES = 40


def _excerpt(task: dict[str, Any]) -> html.Div:
    lines = task.get("excerpt_lines") or []
    error_index = task.get("error_line_index")
    rendered = []
    for index, line in enumerate(lines[:MAX_EXCERPT_LINES]):
        classes = ["log-line"]
        if error_index is not None and index == error_index:
            classes.append("log-line--error")
        rendered.append(
            html.Div(
                [
                    html.Span(f"{index + 1:>2}", className="log-gutter"),
                    html.Span(line if line else " ", className="log-text"),
                ],
                className=" ".join(classes),
            )
        )
    return html.Div(rendered, className="log-block", role="log", **{"aria-label": "Log excerpt"})


def _task_card(task: dict[str, Any]) -> html.Div:
    notes = [
        html.Span(f"try {task['try_number']}", className="log-meta-item"),
        html.Span(format_duration(task["duration_seconds"]), className="log-meta-item mono"),
    ]
    if task.get("log_truncated"):
        notes.append(
            html.Span(
                f"showing last {task['excerpt_line_count']} of {task['total_log_lines']:,} lines",
                className="log-meta-item log-meta-item--note",
            )
        )
    return html.Div(
        [
            html.Div(
                [
                    html.H3(task["task_id"], className="log-task-id mono"),
                    html.Div(notes, className="log-meta"),
                ],
                className="log-task-head",
            ),
            _excerpt(task),
        ],
        className="log-task",
    )


def log_panel(
    dag_id: str | None,
    payload: dict[str, Any] | None,
    close_href: str,
    error: str | None = None,
) -> html.Section:
    close_link = html.A("Close", href=close_href, className="btn btn--ghost btn--sm")
    if dag_id is None:
        return html.Section()
    if error:
        header = components.panel_header("Failed task logs", "The log query failed.", right=close_link)
        return html.Section(
            [header, components.empty_state("Logs could not be loaded", error)],
            className="panel log-panel",
            id="log-panel",
        )
    if payload is None:
        header = components.panel_header("Failed task logs", "That run is not in the mirror.", right=close_link)
        return html.Section(
            [
                header,
                components.empty_state(
                    "Run not found",
                    "The selected run no longer exists in the mirror. Pick a failed run from the timeline.",
                ),
            ],
            className="panel log-panel",
            id="log-panel",
        )

    run = payload["run"]
    tasks = payload["failed_tasks"]
    subtitle = (
        f"{run['run_id']} · logical {format_datetime(run['logical_date'])} · "
        f"{len(tasks)} failed task{'s' if len(tasks) != 1 else ''}"
    )
    header = components.panel_header("Failed task logs", subtitle, right=close_link)
    if not tasks:
        return html.Section(
            [
                header,
                components.empty_state(
                    "This run has no failed tasks",
                    "Every task in this run finished successfully. Close the panel to return to the timeline.",
                ),
            ],
            className="panel log-panel",
            id="log-panel",
        )
    return html.Section(
        [header, html.Div([_task_card(task) for task in tasks], className="log-tasks")],
        className="panel log-panel",
        id="log-panel",
    )


def close_href_for(dag_id: str | None, run_id: str | None) -> str:
    if dag_id and run_id:
        return f"/dashboard?dag={quote(dag_id, safe='')}&run={quote(run_id, safe=':')}"
    return "/dashboard"
