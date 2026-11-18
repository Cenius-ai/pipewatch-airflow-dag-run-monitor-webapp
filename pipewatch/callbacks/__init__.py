"""Callback registration entry point (imported once by app.py)."""

from __future__ import annotations

from . import auth as auth_callbacks
from . import panel as panel_callbacks
from . import shell as shell_callbacks


def register_all_callbacks(dash_app) -> None:
    auth_callbacks.register(dash_app)
    shell_callbacks.register(dash_app)
    panel_callbacks.register(dash_app)
