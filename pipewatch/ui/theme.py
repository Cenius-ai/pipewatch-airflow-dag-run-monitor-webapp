"""Design tokens, formatters and the Plotly theme for Pipewatch.

The palette is the committed "Dark Precision (OLED)" direction: near-black
layered surfaces, one saturated accent, tabular numerals, legend-free chrome.
Chart libraries only ever receive hex values (never oklch()/var()).
"""

from __future__ import annotations

from datetime import datetime, timezone

import plotly.io as pio

PRODUCT_NAME = "Pipewatch"
PRODUCT_TAGLINE = "Airflow DAG Run Monitor"

COLORS = {
    "background": "#0a0c11",
    "card": "#15171c",
    "overlay": "#1c1c21",
    "muted": "#1f2227",
    "border": "#2b2e33",
    "foreground": "#eef0f4",
    "card_foreground": "#eef0f4",
    "muted_foreground": "#9b9fa5",
    "primary": "#e3e5e8",
    "on_primary": "#111111",
    "secondary": "#1f2227",
    "on_secondary": "#eef0f4",
    "accent": "#ed7940",
    "on_accent": "#111111",
    "ring": "#ed7940",
    "destructive": "#c9302d",
    "on_destructive": "#ffffff",
}

STATE_COLORS = {
    "success": "#4ade80",
    "failed": "#f07070",
    "running": COLORS["accent"],
}

CHART_SERIES = {
    "p95": COLORS["accent"],
    "p50": "#8b93a1",
    "grid": "#23262c",
}

FONT_STACK = "'Lexend', 'Segoe UI', system-ui, -apple-system, sans-serif"

INDEX_STRING = """<!DOCTYPE html>
<html lang="en">
  <head>
    {%metas%}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Pipewatch — a lightweight run-health dashboard for Airflow DAG runs, task latency and SLA misses.">
    <meta name="color-scheme" content="dark">
    <title>{%title%}</title>
    {%favicon%}
    <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
    {%css%}
  </head>
  <body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
  </body>
</html>
"""


# Shared chart chrome as a plain layout dict: every figure we render is styled
# with these committed tokens (hex only — canvas libraries cannot parse oklch()).
PLOTLY_LAYOUT: dict = {
    "colorway": [COLORS["accent"], "#8b93a1", "#6ea8fe", "#4ade80"],
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": FONT_STACK, "size": 12, "color": COLORS["muted_foreground"]},
    "margin": {"l": 8, "r": 12, "t": 28, "b": 8},
    "hoverlabel": {
        "bgcolor": COLORS["overlay"],
        "bordercolor": COLORS["border"],
        "font": {"family": FONT_STACK, "size": 12, "color": COLORS["foreground"]},
    },
    "xaxis": {
        "gridcolor": CHART_SERIES["grid"],
        "zeroline": False,
        "tickfont": {"size": 11, "color": COLORS["muted_foreground"]},
        "linecolor": COLORS["border"],
    },
    "yaxis": {
        "gridcolor": CHART_SERIES["grid"],
        "zeroline": False,
        "rangemode": "tozero",
        "tickfont": {"size": 11, "color": COLORS["muted_foreground"]},
        "linecolor": COLORS["border"],
    },
    "legend": {
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "x": 0,
        "font": {"size": 11, "color": COLORS["muted_foreground"]},
    },
}


def apply_plotly_theme() -> None:
    """Pick Plotly's dark base; ``style_figure`` layers the committed tokens on top."""
    pio.templates.default = "plotly_dark"


def style_figure(figure):
    """Apply Pipewatch's chart chrome to one figure and return it."""
    figure.update_layout(**PLOTLY_LAYOUT)
    return figure


def format_duration(seconds: float | int | None) -> str:
    """Human duration: 48s · 22m 08s · 1h 04m."""
    if seconds is None:
        return "—"
    total = int(round(float(seconds)))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def format_number(value: float | int, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def _parse(iso_timestamp: str | datetime | None) -> datetime | None:
    if iso_timestamp is None:
        return None
    if isinstance(iso_timestamp, datetime):
        return iso_timestamp
    try:
        return datetime.fromisoformat(str(iso_timestamp))
    except ValueError:
        return None


def format_datetime(iso_timestamp: str | datetime | None) -> str:
    """18 Nov 2026, 00:02 UTC — never a raw ISO string on screen."""
    parsed = _parse(iso_timestamp)
    if parsed is None:
        return "—"
    return parsed.strftime("%d %b %Y, %H:%M UTC")


def format_short_datetime(iso_timestamp: str | datetime | None) -> str:
    parsed = _parse(iso_timestamp)
    if parsed is None:
        return "—"
    return parsed.strftime("%d %b · %H:%M")


def format_relative(iso_timestamp: str | datetime | None) -> str:
    """Clamped relative time: 'just now', '3 days ago', then an absolute date."""
    parsed = _parse(iso_timestamp)
    if parsed is None:
        return "—"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta_seconds = (now - parsed).total_seconds()
    if delta_seconds < 90:
        return "just now"
    if delta_seconds < 3600:
        minutes = int(delta_seconds // 60)
        return f"{minutes} min ago"
    if delta_seconds < 86400:
        hours = int(delta_seconds // 3600)
        return f"{hours} h ago"
    days = int(delta_seconds // 86400)
    if days == 1:
        return "yesterday"
    if days < 21:
        return f"{days} days ago"
    return parsed.strftime("%d %b %Y")


def format_run_id(run_id: str) -> str:
    """`scheduled__2026-11-18T00:00:00` → `scheduled · 18 Nov 00:00`."""
    if "__" not in run_id:
        return run_id
    prefix, _, stamp = run_id.partition("__")
    parsed = _parse(stamp)
    if parsed is None:
        return run_id
    return f"{prefix} · {parsed.strftime('%d %b %H:%M')}"
