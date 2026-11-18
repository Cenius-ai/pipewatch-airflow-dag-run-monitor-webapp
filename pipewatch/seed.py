"""Deterministic demo dataset for Pipewatch.

The seed is idempotent: running it twice inserts nothing new. It is called from
the normal boot path (`bootstrap_database`) and by `python3 -m pipewatch.seed`,
so a bare `python3 app.py` on a fresh clone always renders a populated app.

No Airflow connection is involved: every row below is generated locally from a
fixed random seed so screenshots, tests and the demo are reproducible.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from . import db
from .auth import hash_password, verify_password
from .models import Dag, DagRun, SlaMiss, TaskInstance, User
from .stats import percentile

DEMO_ACCOUNTS = [
    {
        "username": "cenius",
        "email": "cenius@cenius.ai",
        "password": "cenius",
        "display_name": "Cenius Operator",
        "role": "admin",
    },
    {
        "username": "airflow",
        "email": "airflow@pipewatch.dev",
        "password": "airflow-demo",
        "display_name": "Demo Operator",
        "role": "operator",
    },
]

RUNS_PER_DAG = 30
EXCERPT_LINES = 40

DAG_SPECS = [
    {
        "dag_id": "load_events_daily",
        "owner": "alice.chen",
        "description": "Land clickstream events from the ingestion bucket into the warehouse.",
        "schedule_interval": "@daily",
        "sla_percentile": 0.78,
        "tasks": [
            ("check_landing_manifest", 52),
            ("stage_raw_events", 268),
            ("validate_event_schema", 121),
            ("dedupe_events", 332),
            ("load_event_facts", 196),
        ],
    },
    {
        "dag_id": "transform_events_hourly",
        "owner": "alice.chen",
        "description": "Hourly sessionisation and event model rebuilds over staged events.",
        "schedule_interval": "@hourly",
        "sla_percentile": 0.76,
        "tasks": [
            ("extract_hourly_events", 78),
            ("build_session_windows", 236),
            ("run_event_models", 302),
            ("publish_session_facts", 104),
        ],
    },
    {
        "dag_id": "orders_reconciliation",
        "owner": "marcus.oduya",
        "description": "Reconcile gateway settlements against warehouse order records.",
        "schedule_interval": "@daily",
        "sla_percentile": 0.8,
        "tasks": [
            ("pull_gateway_settlements", 164),
            ("pull_warehouse_orders", 147),
            ("reconcile_settlements", 368),
            ("flag_mismatched_orders", 92),
            ("write_reconciliation_report", 71),
        ],
    },
    {
        "dag_id": "warehouse_sync_nightly",
        "owner": "marcus.oduya",
        "description": "Nightly dimension sync and fact partition rebuild for the reporting marts.",
        "schedule_interval": "@daily",
        "sla_percentile": 0.75,
        "tasks": [
            ("vacuum_staging_tables", 118),
            ("sync_dimension_tables", 279),
            ("rebuild_fact_partitions", 624),
            ("analyze_table_statistics", 171),
        ],
    },
    {
        "dag_id": "publish_metrics_daily",
        "owner": "priya.raman",
        "description": "Roll up product metrics and publish the daily executive snapshot.",
        "schedule_interval": "@daily",
        "sla_percentile": 0.79,
        "tasks": [
            ("collect_run_statistics", 92),
            ("refresh_metric_rollups", 331),
            ("export_dashboard_snapshot", 138),
        ],
    },
    {
        "dag_id": "ml_feature_refresh",
        "owner": "priya.raman",
        "description": "Rebuild churn-model feature tables and refresh feature-store snapshots.",
        "schedule_interval": "@daily",
        "sla_percentile": 0.77,
        "tasks": [
            ("build_customer_features", 462),
            ("score_churn_model", 318),
            ("write_feature_snapshots", 176),
            ("validate_feature_drift", 122),
        ],
    },
]

FAILURE_TEMPLATES = [
    {
        "error_type": "psycopg2.errors.DeadlockDetected",
        "message": "deadlock detected",
        "detail": [
            "DETAIL:  Process 5123 waits for ShareLock on transaction 991; blocked by process 5188.",
            "HINT:  See server log for query details.",
        ],
        "progress": "batch {batch}/{batches}: merging staging rows",
    },
    {
        "error_type": "pipeline.exceptions.SchemaDriftError",
        "message": "column 'event_ts' changed type from TIMESTAMP to VARCHAR",
        "detail": [
            "expected: TIMESTAMP(6), received: VARCHAR(64)",
            "source: s3://pipewatch-landing/events/dt={dt}/",
        ],
        "progress": "validating upstream schema revision {batch}",
    },
    {
        "error_type": "socket.timeout",
        "message": "HTTPSConnectionPool(host='gateway.internal', port=443): read timed out. (read timeout=120)",
        "detail": [
            "request: POST /v2/settlements/export",
            "retry 3 of 3 exhausted",
        ],
        "progress": "requesting settlement export page {batch}",
    },
    {
        "error_type": "airflow.exceptions.AirflowTaskTimeout",
        "message": "Task exceeded max execution time (3600s)",
        "detail": [
            "task execution timeout, execution_time=3612.44s",
        ],
        "progress": "partition {batch}/{batches}: rebuilding fact rows",
    },
    {
        "error_type": "ValueError",
        "message": "feature frame has 0 rows after filtering label window",
        "detail": [
            "label_window_days=90, source_rows=0",
            "upstream snapshot ml_customer_events is empty for the window",
        ],
        "progress": "assembling feature frame for window {batch}",
    },
]

LOG_HEADER = [
    "[{ts}] {{standard_task_runner.py:104}} INFO - Running: ['airflow', 'tasks', 'run', '{dag}', '{task}', '{logical}', '--job-id', '{job_id}', '--pool', 'default_pool', '--subdir', 'DAGS_FOLDER/{dag}.py']",
    "[{ts}] {{taskinstance.py:1179}} INFO - Dependencies all met for dep_context=non-requeueable deps",
    "[{ts}] {{taskinstance.py:1383}} INFO - Starting attempt {attempt} of 3",
    "[{ts}] {{pod_manager.py:209}} INFO - [base] starting main container for pod \"{pod}\"",
    "[{ts}] {{taskinstance.py:1095}} INFO - Exporting env vars: AIRFLOW_CTX_DAG_ID={dag}",
    "[{ts}] {{{task}.py:41}} INFO - {first_step}",
]


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)


def _stamp(base: datetime, offset_seconds: int) -> str:
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%d, %H:%M:%S UTC")


def _build_excerpt(
    rng: random.Random,
    dag_id: str,
    task_id: str,
    logical_date: datetime,
    attempt: int,
) -> dict:
    """Build one failed task's log excerpt with the error line index recorded."""
    template = rng.choice(FAILURE_TEMPLATES)
    batches = rng.randint(4, 12)
    batch = rng.randint(2, batches - 1)
    start = logical_date + timedelta(seconds=rng.randint(30, 400))

    lines: list[str] = []
    for index, header in enumerate(LOG_HEADER):
        lines.append(
            header.format(
                ts=_stamp(start, index * 3),
                dag=dag_id,
                task=task_id,
                logical=logical_date.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                job_id=rng.randint(120000, 990000),
                attempt=attempt,
                pod=f"{dag_id}.{task_id}.{rng.randrange(16**8):08x}",
                first_step=rng.choice(
                    [
                        "reading run configuration",
                        "resolving upstream partitions",
                        "opening warehouse session pool",
                    ]
                ),
            )
        )

    for step in range(rng.randint(15, 20)):
        lines.append(
            "[{ts}] {{{task}.py:{line}}} INFO - {progress}".format(
                ts=_stamp(start, 20 + step * 11),
                task=task_id,
                line=57 + (step % 12) * 9,
                progress=template["progress"].format(
                    batch=min(batches, batch + step), batches=batches
                ),
            )
        )

    trace_lines = [
        "Traceback (most recent call last):",
        f'  File "/opt/airflow/dags/{dag_id}.py", line 214, in {task_id}',
        "    run_step(context)",
        '  File "/opt/airflow/plugins/pipeline/steps.py", line 138, in run_step',
        "    self._execute_batches(batches)",
        '  File "/opt/airflow/plugins/pipeline/steps.py", line 96, in _execute_batches',
        "    cursor.execute(self.statement, params)",
    ]
    lines.extend(trace_lines)
    error_line = f"{template['error_type']}: {template['message']}"
    lines.append(error_line)
    error_index = len(lines) - 1
    lines.extend(template["detail"])
    lines.append(
        "[{ts}] {{taskinstance.py:1383}} ERROR - Task failed with exception".format(
            ts=_stamp(start, 3200)
        )
    )

    truncated = rng.random() < 0.8
    excerpt = lines[:EXCERPT_LINES]
    if error_index >= len(excerpt):  # keep the error line inside the window
        excerpt = lines[: error_index + 1][-EXCERPT_LINES:]
        error_index = len(excerpt) - 1
    total_lines = len(excerpt) + (rng.randint(180, 640) if truncated else 0)

    return {
        "log_excerpt": "\n".join(excerpt),
        "error_line_index": error_index,
        "log_truncated": truncated,
        "total_log_lines": total_lines,
        "excerpt_line_count": len(excerpt),
    }


def _logical_dates(schedule_interval: str, count: int, anchor: datetime) -> list[datetime]:
    if schedule_interval == "@hourly":
        newest = anchor.replace(minute=0, second=0)
        return [newest - timedelta(hours=offset) for offset in range(count)]
    newest = anchor.replace(hour=0, minute=0, second=0)
    return [newest - timedelta(days=offset) for offset in range(count)]


def _build_runs(dag_spec: dict, dag_index: int, anchor: datetime) -> list[dict]:
    rng = random.Random(7_331 + dag_index * 977)
    logical_dates = _logical_dates(dag_spec["schedule_interval"], RUNS_PER_DAG, anchor)
    failed_offsets = set(rng.sample(range(2, RUNS_PER_DAG), 4))
    running_offsets = {0} if dag_index % 3 == 0 else set()

    runs: list[dict] = []
    for offset, logical_date in enumerate(logical_dates):
        if offset in running_offsets:
            state = "running"
        elif offset in failed_offsets:
            state = "failed"
        else:
            state = "success"

        tasks: list[dict] = []
        fail_at = rng.randrange(len(dag_spec["tasks"])) if state == "failed" else None
        for task_index, (task_id, base_seconds) in enumerate(dag_spec["tasks"]):
            if fail_at is not None and task_index > fail_at:
                break
            multiplier = rng.uniform(0.62, 1.55)
            if rng.random() < 0.14:  # occasional slow outlier lifts p95 above p50
                multiplier *= rng.uniform(1.6, 2.4)
            duration = max(3, int(base_seconds * multiplier))
            task_state = "success"
            attempt = 1
            if fail_at is not None and task_index == fail_at:
                task_state = "failed"
                attempt = rng.randint(1, 2)
            if state == "running" and task_index == len(dag_spec["tasks"]) - 1:
                task_state = "running"
            tasks.append(
                {
                    "task_id": task_id,
                    "state": task_state,
                    "try_number": attempt,
                    "duration_seconds": duration,
                }
            )

        duration = sum(task["duration_seconds"] for task in tasks) + rng.randint(8, 26)
        start_time = logical_date + timedelta(seconds=rng.randint(15, 180))
        end_time = None if state == "running" else start_time + timedelta(seconds=duration)

        for task in tasks:
            if state == "running" and task["state"] == "running":
                task["duration_seconds"] = max(1, int(duration * 0.4))
            if task["state"] == "failed":
                task.update(
                    _build_excerpt(
                        rng,
                        dag_spec["dag_id"],
                        task["task_id"],
                        logical_date,
                        task["try_number"],
                    )
                )
            else:
                task.update(
                    {
                        "log_excerpt": "",
                        "error_line_index": None,
                        "log_truncated": False,
                        "total_log_lines": 0,
                        "excerpt_line_count": 0,
                    }
                )

        runs.append(
            {
                "run_id": f"scheduled__{logical_date.strftime('%Y-%m-%dT%H:%M:%S')}",
                "logical_date": logical_date,
                "state": state,
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration,
                "tasks": tasks,
            }
        )
    return runs


def _seed_users(db_session) -> int:
    created = 0
    for account in DEMO_ACCOUNTS:
        existing = db_session.execute(
            select(User).where(User.username == account["username"])
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db_session.add(
            User(
                username=account["username"],
                email=account["email"],
                password_hash=hash_password(account["password"]),
                display_name=account["display_name"],
                role=account["role"],
                created_at=_utcnow_naive(),
            )
        )
        created += 1
    db_session.flush()
    return created


def _seed_pipeline_data(db_session, anchor: datetime) -> dict[str, int]:
    counts = {"dags": 0, "runs": 0, "tasks": 0, "sla_misses": 0}
    for dag_index, dag_spec in enumerate(DAG_SPECS):
        runs = _build_runs(dag_spec, dag_index, anchor)
        completed = [run["duration_seconds"] for run in runs if run["state"] != "running"]
        sla_seconds = int(round(percentile(completed, dag_spec["sla_percentile"]) / 30.0)) * 30
        sla_seconds = max(60, sla_seconds)

        db_session.add(
            Dag(
                dag_id=dag_spec["dag_id"],
                owner=dag_spec["owner"],
                description=dag_spec["description"],
                schedule_interval=dag_spec["schedule_interval"],
                sla_minutes=max(1, round(sla_seconds / 60)),
            )
        )
        counts["dags"] += 1
        db_session.flush()

        for run in runs:
            run["sla_met"] = run["state"] != "running" and run["duration_seconds"] <= sla_seconds
            db_session.add(
                DagRun(
                    dag_id=dag_spec["dag_id"],
                    run_id=run["run_id"],
                    logical_date=run["logical_date"],
                    state=run["state"],
                    start_time=run["start_time"],
                    end_time=run["end_time"],
                    duration_seconds=run["duration_seconds"],
                    sla_met=run["sla_met"],
                )
            )
            counts["runs"] += 1
            db_session.flush()

            slowest_task = max(run["tasks"], key=lambda item: item["duration_seconds"])
            for task in run["tasks"]:
                db_session.add(
                    TaskInstance(
                        dag_id=dag_spec["dag_id"],
                        run_id=run["run_id"],
                        task_id=task["task_id"],
                        state=task["state"],
                        try_number=task["try_number"],
                        duration_seconds=task["duration_seconds"],
                        log_excerpt=task["log_excerpt"],
                        log_truncated=task["log_truncated"],
                        total_log_lines=task["total_log_lines"],
                        excerpt_line_count=task["excerpt_line_count"],
                        error_line_index=task["error_line_index"],
                    )
                )
                counts["tasks"] += 1

            if run["sla_met"] or run["end_time"] is None:
                continue
            overage = run["duration_seconds"] - sla_seconds
            late_task = slowest_task if run["state"] == "failed" else None
            db_session.add(
                SlaMiss(
                    dag_id=dag_spec["dag_id"],
                    run_id=run["run_id"],
                    task_id=late_task["task_id"] if late_task else slowest_task["task_id"],
                    owner=dag_spec["owner"],
                    sla_threshold_seconds=sla_seconds,
                    missed_by_seconds=overage,
                    detected_at=run["end_time"] + timedelta(minutes=1),
                )
            )
            counts["sla_misses"] += 1
    return counts


def table_counts() -> dict[str, int]:
    with db.session_scope() as db_session:
        return {
            "users": db_session.execute(select(func.count()).select_from(User)).scalar_one(),
            "dags": db_session.execute(select(func.count()).select_from(Dag)).scalar_one(),
            "runs": db_session.execute(select(func.count()).select_from(DagRun)).scalar_one(),
            "tasks": db_session.execute(
                select(func.count()).select_from(TaskInstance)
            ).scalar_one(),
            "sla_misses": db_session.execute(
                select(func.count()).select_from(SlaMiss)
            ).scalar_one(),
        }


def seed() -> dict[str, int]:
    """Insert the demo dataset when it is missing. Safe to call repeatedly."""
    db.init_db()
    anchor = _utcnow_naive()
    with db.session_scope() as db_session:
        _seed_users(db_session)
        existing_dags = db_session.execute(select(func.count()).select_from(Dag)).scalar_one()
        if existing_dags == 0:
            _seed_pipeline_data(db_session, anchor)
        else:
            # DAG rows exist but task instances may not: fill in a partially seeded file.
            existing_tasks = db_session.execute(
                select(func.count()).select_from(TaskInstance)
            ).scalar_one()
            if existing_tasks == 0:
                for dag_spec in DAG_SPECS:
                    dag = db_session.get(Dag, dag_spec["dag_id"])
                    if dag is not None:
                        db_session.delete(dag)
                db_session.flush()
                _seed_pipeline_data(db_session, anchor)
    return table_counts()


def seed_if_empty() -> dict[str, int]:
    db.init_db()
    counts = table_counts()
    if counts["dags"] > 0 and counts["users"] > 0:
        with db.session_scope() as db_session:
            _seed_users(db_session)
        return counts
    return seed()


def verify_demo_login() -> None:
    """Fail loudly if the seeded demo account cannot authenticate."""
    with db.session_scope() as db_session:
        user = db_session.execute(
            select(User).where(User.username == DEMO_ACCOUNTS[0]["username"])
        ).scalar_one_or_none()
        if user is None:
            raise SystemExit("seed failed: demo user 'cenius' is missing")
        if not verify_password(user.password_hash, DEMO_ACCOUNTS[0]["password"]):
            raise SystemExit("seed failed: the demo password does not verify")


def main() -> int:
    counts = seed()
    verify_demo_login()
    print("Pipewatch demo data ready:")
    for table, count in counts.items():
        print(f"  {table:>11}: {count}")
    print("Demo sign-in: username cenius (cenius@cenius.ai) — password shown on the sign-in card.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
