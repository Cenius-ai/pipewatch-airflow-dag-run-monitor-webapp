"""Read-only query service shared by the JSON API and the Dash callbacks.

Every function returns plain JSON-ready dicts so the HTTP routes and the tab
callbacks cannot drift apart (they consume the exact same shapes).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select

from .. import db
from ..models import Dag, DagRun, SlaMiss, TaskInstance
from ..stats import percentile

DEFAULT_RUN_LIMIT = 30
DEFAULT_STATS_WINDOW = 30
DEFAULT_SLA_LIMIT = 50


def _iso(value) -> str | None:
    return value.isoformat(timespec="seconds") if value is not None else None


def list_dags() -> list[dict[str, Any]]:
    """All DAGs with their run count and most recent run state."""
    with db.session_scope() as session:
        dags = session.execute(select(Dag).order_by(Dag.dag_id)).scalars().all()
        result = []
        for dag in dags:
            run_count = session.execute(
                select(func.count()).select_from(DagRun).where(DagRun.dag_id == dag.dag_id)
            ).scalar_one()
            latest = (
                session.execute(
                    select(DagRun)
                    .where(DagRun.dag_id == dag.dag_id)
                    .order_by(DagRun.logical_date.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            result.append(
                {
                    "dag_id": dag.dag_id,
                    "owner": dag.owner,
                    "description": dag.description,
                    "schedule_interval": dag.schedule_interval,
                    "sla_minutes": dag.sla_minutes,
                    "run_count": run_count,
                    "last_run_state": latest.state if latest else None,
                    "last_run_at": _iso(latest.logical_date) if latest else None,
                }
            )
        return result


def dag_exists(dag_id: str) -> bool:
    with db.session_scope() as session:
        return session.get(Dag, dag_id) is not None


def get_dag(dag_id: str) -> dict[str, Any] | None:
    with db.session_scope() as session:
        dag = session.get(Dag, dag_id)
        if dag is None:
            return None
        run_count = session.execute(
            select(func.count()).select_from(DagRun).where(DagRun.dag_id == dag_id)
        ).scalar_one()
        latest = (
            session.execute(
                select(DagRun)
                .where(DagRun.dag_id == dag_id)
                .order_by(DagRun.logical_date.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        return {
            "dag_id": dag.dag_id,
            "owner": dag.owner,
            "description": dag.description,
            "schedule_interval": dag.schedule_interval,
            "sla_minutes": dag.sla_minutes,
            "run_count": run_count,
            "last_run_state": latest.state if latest else None,
            "last_run_at": _iso(latest.logical_date) if latest else None,
        }


def list_runs(dag_id: str, limit: int = DEFAULT_RUN_LIMIT) -> list[dict[str, Any]] | None:
    """Most recent runs for a DAG, newest first. None when the DAG is unknown."""
    with db.session_scope() as session:
        if session.get(Dag, dag_id) is None:
            return None
        runs = (
            session.execute(
                select(DagRun)
                .where(DagRun.dag_id == dag_id)
                .order_by(DagRun.logical_date.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        failed_counts = dict(
            session.execute(
                select(TaskInstance.run_id, func.count())
                .where(TaskInstance.dag_id == dag_id, TaskInstance.state == "failed")
                .group_by(TaskInstance.run_id)
            ).all()
        )
        return [
            {
                "dag_id": run.dag_id,
                "run_id": run.run_id,
                "state": run.state,
                "logical_date": _iso(run.logical_date),
                "start_time": _iso(run.start_time),
                "end_time": _iso(run.end_time),
                "duration_seconds": run.duration_seconds,
                "sla_met": bool(run.sla_met),
                "failed_task_count": int(failed_counts.get(run.run_id, 0)),
            }
            for run in runs
        ]


def task_stats(dag_id: str, window: int = DEFAULT_STATS_WINDOW) -> list[dict[str, Any]] | None:
    """Per-task p50/p95 over the most recent `window` runs, ranked by p95 desc."""
    with db.session_scope() as session:
        if session.get(Dag, dag_id) is None:
            return None
        runs = (
            session.execute(
                select(DagRun.run_id, DagRun.logical_date)
                .where(DagRun.dag_id == dag_id)
                .order_by(DagRun.logical_date.desc())
                .limit(window)
            )
            .all()
        )
        if not runs:
            return []
        run_ids = [run.run_id for run in runs]
        rows = session.execute(
            select(
                TaskInstance.task_id,
                TaskInstance.duration_seconds,
                TaskInstance.state,
                DagRun.logical_date,
            )
            .join(
                DagRun,
                (DagRun.dag_id == TaskInstance.dag_id) & (DagRun.run_id == TaskInstance.run_id),
            )
            .where(TaskInstance.dag_id == dag_id, TaskInstance.run_id.in_(run_ids))
            .order_by(DagRun.logical_date.desc())
        ).all()

        durations: dict[str, list[int]] = defaultdict(list)
        last_state: dict[str, str] = {}
        for task_id, duration_seconds, state, _logical in rows:
            durations[task_id].append(duration_seconds)
            last_state.setdefault(task_id, state)

        stats = [
            {
                "task_id": task_id,
                "p50_seconds": percentile(values, 0.5),
                "p95_seconds": percentile(values, 0.95),
                "max_seconds": max(values),
                "run_count": len(values),
                "last_state": last_state[task_id],
            }
            for task_id, values in durations.items()
        ]
        stats.sort(key=lambda item: (-item["p95_seconds"], item["task_id"]))
        return stats


def failed_tasks(dag_id: str, run_id: str) -> dict[str, Any] | None:
    """Failed task instances of one run with their log excerpt. None if unknown."""
    with db.session_scope() as session:
        run = session.execute(
            select(DagRun).where(DagRun.dag_id == dag_id, DagRun.run_id == run_id)
        ).scalar_one_or_none()
        if run is None:
            return None
        tasks = (
            session.execute(
                select(TaskInstance)
                .where(
                    TaskInstance.dag_id == dag_id,
                    TaskInstance.run_id == run_id,
                    TaskInstance.state == "failed",
                )
                .order_by(TaskInstance.task_id)
            )
            .scalars()
            .all()
        )
        return {
            "dag_id": dag_id,
            "run_id": run_id,
            "run": {
                "run_id": run.run_id,
                "state": run.state,
                "logical_date": _iso(run.logical_date),
                "start_time": _iso(run.start_time),
                "end_time": _iso(run.end_time),
                "duration_seconds": run.duration_seconds,
            },
            "failed_tasks": [
                {
                    "task_id": task.task_id,
                    "try_number": task.try_number,
                    "duration_seconds": task.duration_seconds,
                    "excerpt_lines": task.log_excerpt.split("\n") if task.log_excerpt else [],
                    "log_truncated": bool(task.log_truncated),
                    "total_log_lines": task.total_log_lines,
                    "excerpt_line_count": task.excerpt_line_count,
                    "error_line_index": task.error_line_index,
                }
                for task in tasks
            ],
        }


def list_owners() -> list[str]:
    with db.session_scope() as session:
        sla_owners = set(session.execute(select(SlaMiss.owner).distinct()).scalars().all())
        dag_owners = set(session.execute(select(Dag.owner).distinct()).scalars().all())
        return sorted(sla_owners | dag_owners)


def sla_misses(owner: str | None = None, limit: int = DEFAULT_SLA_LIMIT) -> dict[str, Any]:
    """SLA misses newest first, optionally filtered by owner."""
    owner_filter = (owner or "all").strip()
    with db.session_scope() as session:
        query = select(SlaMiss)
        count_query = select(func.count()).select_from(SlaMiss)
        if owner_filter and owner_filter != "all":
            query = query.where(SlaMiss.owner == owner_filter)
            count_query = count_query.where(SlaMiss.owner == owner_filter)
        total = session.execute(count_query).scalar_one()
        misses = (
            session.execute(query.order_by(SlaMiss.detected_at.desc()).limit(limit))
            .scalars()
            .all()
        )
        return {
            "misses": [
                {
                    "id": miss.id,
                    "dag_id": miss.dag_id,
                    "run_id": miss.run_id,
                    "task_id": miss.task_id,
                    "owner": miss.owner,
                    "sla_threshold_seconds": miss.sla_threshold_seconds,
                    "missed_by_seconds": miss.missed_by_seconds,
                    "detected_at": _iso(miss.detected_at),
                }
                for miss in misses
            ],
            "owners": list_owners(),
            "filters": {"owner": owner_filter or "all"},
            "total": total,
            "returned": len(misses),
            "limit": limit,
        }
