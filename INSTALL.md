# Installing Pipewatch

Pipewatch is a single Python 3.11 service. The dependency manifest is
`requirements.txt` at the repository root and the only package manager involved is **pip**
(every pin is a real released version, so the install is reproducible).

## Prerequisites

- **Python 3.11+** with `pip` (`python3 --version`, `python3 -m pip --version`).
- SQLite support in the standard library (shipped with CPython — nothing to install).
- No database server, no Node.js, no Docker, no network access at runtime.

## Step 1 — Install (dependencies → schema → demo data)

```bash
sh install.sh
```

`install.sh` runs `pip install -r requirements.txt`, writes a random `SECRET_KEY` into `.env` when
one does not exist, creates the SQLite schema, seeds the deterministic demo dataset, and **exits**.
It is safe to run again.

Manual equivalent:

```bash
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
python3 -m pipewatch.seed          # create the schema + demo rows, then exit
```

## Step 2 — Seed (already done by step 1; run again any time)

```bash
python3 -m pipewatch.seed
```

Idempotent: it inserts nothing when the data is already present, verifies that the seeded demo
password hash validates, and never starts the HTTP server.

## Step 3 — Run in development

```bash
python3 app.py
# Pipewatch listening on 0.0.0.0:8050
```

Open <http://127.0.0.1:8050> and sign in with `cenius` / `cenius`
(email `cenius@cenius.ai`) — or `airflow` / `airflow-demo`.

The port comes from `$PORT` with `8050` as the fallback, and the server always binds `0.0.0.0`:

```bash
PORT=9000 python3 app.py
```

## Step 4 — Tests

```bash
python3 -m pytest
```

The suite uses a throwaway SQLite file in a temporary directory (it never touches
`pipewatch.db`) and covers the seed, the auth guard, cookie attributes, the read API contract,
the three-tab layout, the panel callbacks and the log viewer.

## Configuration

Copy `.env.example` to `.env` only if you want to override a default:

| Variable | Default | Notes |
| --- | --- | --- |
| `SECRET_KEY` | generated dev key | Session cookie signing key. |
| `DATABASE_URL` | `sqlite:///<project>/pipewatch.db` | Any SQLAlchemy URL; SQLite needs no server. |

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError: dash` | Run step 1 (or `python3 -m pip install -r requirements.txt`). |
| Port already in use | `PORT=8051 python3 app.py`, or stop the other process holding 8050. |
| Login says "Invalid username or password" | Re-run `python3 -m pipewatch.seed`; the demo accounts are `cenius`/`cenius` and `airflow`/`airflow-demo`. |
| Empty dashboard after cloning an old database file | Delete `pipewatch.db` and restart — the boot path recreates and seeds it. |
