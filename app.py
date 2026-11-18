"""Pipewatch — a lightweight Airflow DAG run monitor built with Plotly Dash.

Run it with:  python3 app.py       (binds 0.0.0.0:8050, honours $PORT)
"""

from __future__ import annotations

import os

import dash

from pipewatch.callbacks import register_all_callbacks
from pipewatch.db import bootstrap_database
from pipewatch.ui.layout import serve_layout
from pipewatch.ui.theme import INDEX_STRING, apply_plotly_theme
from pipewatch.web import create_server

app = dash.Dash(
    __name__,
    title="Pipewatch — Airflow DAG Run Monitor",
    update_title=None,
    suppress_callback_exceptions=True,
    assets_folder="assets",
    index_string=INDEX_STRING,
)
server = app.server

apply_plotly_theme()
create_server(server, app)
app.layout = serve_layout
register_all_callbacks(app)

# Create the SQLite schema and idempotently seed demo data on the normal boot path,
# so a bare `python3 app.py` on a fresh clone renders a populated dashboard.
bootstrap_database()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    print(f"Pipewatch listening on 0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False)
