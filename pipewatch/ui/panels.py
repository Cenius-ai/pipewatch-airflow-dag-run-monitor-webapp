"""The three tab panels: run timeline, slowest tasks, SLA misses."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import plotly.graph_objects as go
from dash import html

from ..stats import percentile
from . import components
from .theme import (
    CHART_SERIES,
    COLORS,
    STATE_COLORS,
    style_figure,
    format_datetime,
    format_duration,
    format_relative,
    format_short_datetime,
)

RUN_WINDOW_CAPTION = "last 30 runs"


# --------------------------------------------------------------------------- #
# charts
# --------------------------------------------------------------------------- #
def runs_chart(dag: dict[str, Any], runs: list[dict[str, Any]]) -> go.Figure:
    ordered = list(reversed(runs))  # oldest on the left, newest on the right
    labels = [format_short_datetime(run["logical_date"]) for run in ordered]
    figure = go.Figure()
    for state in ("success", "failed", "running"):
        values = [
            run["duration_seconds"] if run["state"] == state else None for run in ordered
        ]
        if not any(value is not None for value in values):
            continue
        figure.add_trace(
            go.Bar(
                name=state,
                x=labels,
                y=values,
                marker=dict(color=STATE_COLORS[state], line=dict(width=0)),
                hovertemplate="%{x}<br>%{y} s<extra>" + state + "</extra>",
            )
        )
    sla_seconds = dag["sla_minutes"] * 60
    figure.add_hline(
        y=sla_seconds,
        line=dict(color=COLORS["muted_foreground"], width=1, dash="dot"),
        annotation_text=f"SLA {dag['sla_minutes']}m",
        annotation_position="top left",
        annotation_font=dict(size=10, color=COLORS["muted_foreground"]),
    )
    style_figure(figure)
    figure.update_layout(
        height=248,
        bargap=0.34,
        margin=dict(l=10, r=14, t=34, b=6),
        yaxis_title="duration (s)",
        yaxis_title_font=dict(size=11, color=COLORS["muted_foreground"]),
        xaxis=dict(nticks=8),
        showlegend=True,
        legend=dict(orientation="h", y=1.14, x=0),
    )
    return figure


def task_stats_chart(stats: list[dict[str, Any]]) -> go.Figure:
    top = stats[:8][::-1]  # horizontal bars: slowest at the top
    labels = [task["task_id"] for task in top]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            name="p95",
            y=labels,
            x=[task["p95_seconds"] for task in top],
            orientation="h",
            marker=dict(color=CHART_SERIES["p95"], line=dict(width=0)),
            hovertemplate="%{y}<br>p95 %{x} s<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            name="p50",
            y=labels,
            x=[task["p50_seconds"] for task in top],
            orientation="h",
            marker=dict(color=CHART_SERIES["p50"], line=dict(width=0)),
            hovertemplate="%{y}<br>p50 %{x} s<extra></extra>",
        )
    )
    style_figure(figure)
    figure.update_layout(
        height=max(240, 34 * len(top) + 72),
        barmode="group",
        bargap=0.3,
        margin=dict(l=10, r=16, t=34, b=6),
        xaxis_title="seconds",
        xaxis_title_font=dict(size=11, color=COLORS["muted_foreground"]),
        showlegend=True,
        legend=dict(orientation="h", y=1.12, x=0),
    )
    return figure


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #
def _log_link(dag_id: str, run_id: str) -> html.A:
    href = f"/dashboard/logs?dag={quote(dag_id, safe='')}&run={quote(run_id, safe=':')}"
    return html.A("View log", href=href, className="link-action")


def timeline_panel(
    dag: dict[str, Any] | None,
    runs: list[dict[str, Any]],
    error: str | None,
    selected_run_id: str | None,
) -> html.Section:
    tab = "timeline"
    header = components.panel_header(
        "Run timeline",
        f"Most recent {len(runs)} runs of {dag['dag_id']} · newest first" if dag else "Run health per DAG run",
    )
    if dag is None:
        return html.Section(
            [header, components.silent_alert(tab), components.empty_state(
                "No DAGs available", "Seed the demo dataset with python3 -m pipewatch.seed."
            )],
            className="panel",
        )
    if error:
        return html.Section(
            [
                header,
                components.alert(error, tab, retry_visible=True),
                components.empty_state(
                    "Runs could not be loaded",
                    "The runs query failed. Retry, or pick another DAG from the filter bar.",
                ),
            ],
            className="panel",
        )
    if not runs:
        return html.Section(
            [
                header,
                components.silent_alert(tab),
                components.empty_state(
                    "No runs recorded for this DAG",
                    "Pick another DAG from the filter bar, or run the seed to load demo runs.",
                ),
            ],
            className="panel",
        )

    completed = [run for run in runs if run["state"] != "running"]
    succeeded = [run for run in completed if run["state"] == "success"]
    failed = [run for run in completed if run["state"] == "failed"]
    durations = [run["duration_seconds"] for run in completed]
    success_rate = 100.0 * len(succeeded) / len(completed) if completed else 0.0
    p50 = percentile(durations, 0.5)
    p95 = percentile(durations, 0.95)
    sla_seconds = dag["sla_minutes"] * 60

    metrics = components.metric_row(
        [
            components.flag_metric(
                "Success rate",
                f"{success_rate:.0f}%",
                f"{len(succeeded)} of {len(completed)} completed runs",
                tone="metric--good" if success_rate >= 90 else "metric--warn",
            ),
            components.flag_metric(
                "Failed runs",
                str(len(failed)),
                f"in the {RUN_WINDOW_CAPTION}",
                tone="metric--bad" if failed else "",
            ),
            components.flag_metric("P50 duration", format_duration(p50), "median of completed runs"),
            components.flag_metric(
                "P95 duration",
                format_duration(p95),
                f"SLA threshold {dag['sla_minutes']}m",
                tone="metric--warn" if p95 > sla_seconds else "",
            ),
        ]
    )

    rows = []
    for index, run in enumerate(runs):
        is_failed = run["state"] == "failed"
        row_classes = ["row"]
        if is_failed:
            row_classes.append("row--failed")
        if selected_run_id and run["run_id"] == selected_run_id:
            row_classes.append("row--selected")
        action = (
            _log_link(dag["dag_id"], run["run_id"])
            if run["failed_task_count"] > 0
            else html.Span("—", className="muted")
        )
        rows.append(
            html.Tr(
                [
                    html.Td(components.state_badge(run["state"]), className="td"),
                    html.Td(
                        html.Span(run["run_id"], className="mono id-cell"),
                        className="td",
                    ),
                    html.Td(format_datetime(run["logical_date"]), className="td nowrap"),
                    html.Td(format_datetime(run["start_time"]), className="td nowrap"),
                    html.Td(
                        format_duration(run["duration_seconds"]),
                        className="td num mono"
                        + (" mono--over" if run["duration_seconds"] > sla_seconds else ""),
                    ),
                    html.Td(action, className="td td--action"),
                ],
                className=" ".join(row_classes),
                style={"animationDelay": f"{min(index, 8) * 60}ms"},
            )
        )

    return html.Section(
        [
            header,
            components.silent_alert(tab),
            metrics,
            components.chart(runs_chart(dag, runs)),
            components.table(
                ["State", "Run id", "Logical date", "Started", "Duration", "Log"],
                rows,
                f"Most recent runs of {dag['dag_id']}",
                numeric_from=4,
            ),
        ],
        className="panel",
    )


def task_stats_panel(
    dag: dict[str, Any] | None,
    stats: list[dict[str, Any]],
    error: str | None,
) -> html.Section:
    tab = "tasks"
    header = components.panel_header(
        "Slowest tasks",
        f"Ranked by p95 duration across the {RUN_WINDOW_CAPTION} · {dag['dag_id']}"
        if dag
        else "Ranked by p95 duration",
    )
    if dag is None:
        return html.Section(
            [header, components.silent_alert(tab), components.empty_state(
                "No DAGs available", "Seed the demo dataset with python3 -m pipewatch.seed."
            )],
            className="panel",
        )
    if error:
        return html.Section(
            [
                header,
                components.alert(error, tab, retry_visible=True),
                components.empty_state(
                    "Task statistics could not be loaded",
                    "The stats query failed. Retry, or pick another DAG from the filter bar.",
                ),
            ],
            className="panel",
        )
    if not stats:
        return html.Section(
            [
                header,
                components.silent_alert(tab),
                components.empty_state(
                    "No task runs recorded for this DAG",
                    f"There are no task instances in the {RUN_WINDOW_CAPTION}. Pick another DAG from the filter bar.",
                ),
            ],
            className="panel",
        )

    slowest = stats[0]
    p95_values = [task["p95_seconds"] for task in stats]
    metrics = components.metric_row(
        [
            components.flag_metric(
                "Slowest task",
                slowest["task_id"],
                f"p95 {format_duration(slowest['p95_seconds'])}",
                tone="metric--warn",
            ),
            components.flag_metric(
                "Median p95",
                format_duration(percentile(p95_values, 0.5)),
                f"across {len(stats)} tasks",
            ),
            components.flag_metric(
                "Total task runs",
                f"{sum(task['run_count'] for task in stats):,}",
                f"in the {RUN_WINDOW_CAPTION}",
            ),
            components.flag_metric(
                "Window",
                RUN_WINDOW_CAPTION,
                "fixed for this MVP",
            ),
        ]
    )

    rows = []
    for index, task in enumerate(stats):
        rows.append(
            html.Tr(
                [
                    html.Td(str(index + 1), className="td num mono muted"),
                    html.Td(html.Span(task["task_id"], className="mono"), className="td"),
                    html.Td(format_duration(task["p50_seconds"]), className="td num mono"),
                    html.Td(
                        format_duration(task["p95_seconds"]),
                        className="td num mono strong",
                    ),
                    html.Td(f"{task['run_count']}", className="td num mono"),
                    html.Td(components.state_badge(task["last_state"]), className="td"),
                ],
                className="row",
                style={"animationDelay": f"{min(index, 8) * 60}ms"},
            )
        )

    return html.Section(
        [
            header,
            components.silent_alert(tab),
            metrics,
            components.chart(task_stats_chart(stats)),
            components.table(
                ["Rank", "Task", "p50", "p95", "Runs", "Last state"],
                rows,
                f"Task durations for {dag['dag_id']}, ranked by p95 over the {RUN_WINDOW_CAPTION}",
                numeric_from=2,
            ),
        ],
        className="panel",
    )


def sla_panel(
    payload: dict[str, Any] | None,
    owner_value: str,
    error: str | None,
) -> html.Section:
    tab = "sla"
    misses = (payload or {}).get("misses", [])
    total = (payload or {}).get("total", 0)
    header = components.panel_header(
        "SLA misses",
        f"Showing {len(misses)} of {total} misses · newest first",
    )
    if error:
        return html.Section(
            [
                header,
                components.alert(error, tab, retry_visible=True),
                components.empty_state(
                    "SLA misses could not be loaded",
                    "The SLA query failed. Retry, or switch the owner filter.",
                ),
            ],
            className="panel",
        )
    if not misses:
        owner_label = "All owners" if owner_value in (None, "", "all") else owner_value
        return html.Section(
            [
                header,
                components.alert("", tab, retry_visible=False),
                components.empty_state(
                    f"No SLA misses for {owner_label}",
                    "Switch the owner filter back to All owners to see every miss.",
                ),
            ],
            className="panel",
        )

    overages = [miss["missed_by_seconds"] for miss in misses]
    owners = {miss["owner"] for miss in misses}
    metrics = components.metric_row(
        [
            components.flag_metric("Misses", f"{total}", f"showing {len(misses)} of {total}"),
            components.flag_metric(
                "Worst overage",
                format_duration(max(overages)),
                "past the SLA threshold",
                tone="metric--bad",
            ),
            components.flag_metric("Owners affected", str(len(owners)), "in the current filter"),
            components.flag_metric(
                "Median overage",
                format_duration(percentile(overages, 0.5)),
                "across the listed misses",
            ),
        ]
    )

    rows = []
    for index, miss in enumerate(misses):
        rows.append(
            html.Tr(
                [
                    html.Td(
                        [
                            html.Span(format_relative(miss["detected_at"]), className="stacked-strong"),
                            html.Span(format_datetime(miss["detected_at"]), className="stacked-soft"),
                        ],
                        className="td nowrap",
                    ),
                    html.Td(html.Span(miss["dag_id"], className="mono"), className="td"),
                    html.Td(html.Span(miss["run_id"], className="mono id-cell"), className="td"),
                    html.Td(html.Span(miss["task_id"] or "whole DAG", className="mono"), className="td"),
                    html.Td(miss["owner"], className="td"),
                    html.Td(
                        format_duration(miss["sla_threshold_seconds"]),
                        className="td num mono",
                    ),
                    html.Td(
                        "+" + format_duration(miss["missed_by_seconds"]),
                        className="td num mono mono--over",
                    ),
                ],
                className="row",
                style={"animationDelay": f"{min(index, 8) * 60}ms"},
            )
        )

    return html.Section(
        [
            header,
            components.alert("", tab, retry_visible=False),
            metrics,
            components.table(
                ["Detected", "DAG", "Run id", "Task", "Owner", "SLA", "Missed by"],
                rows,
                "SLA misses, newest first",
                numeric_from=5,
            ),
        ],
        className="panel",
    )
