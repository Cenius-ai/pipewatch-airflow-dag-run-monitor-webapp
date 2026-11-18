"""Read-only data endpoints backed by the query service."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import queries

bp = Blueprint("api_data", __name__, url_prefix="/api")

MAX_LIMIT = 200
MAX_WINDOW = 200


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _dag_not_found(dag_id: str):
    return jsonify({"error": "dag_not_found", "dag_id": dag_id}), 404


@bp.get("/dags")
def get_dags():
    return jsonify({"dags": queries.list_dags()})


@bp.get("/dags/<dag_id>/runs")
def get_runs(dag_id: str):
    limit = _bounded_int("limit", queries.DEFAULT_RUN_LIMIT, 1, MAX_LIMIT)
    runs = queries.list_runs(dag_id, limit=limit)
    if runs is None:
        return _dag_not_found(dag_id)
    return jsonify({"dag_id": dag_id, "limit": limit, "runs": runs})


@bp.get("/dags/<dag_id>/task-stats")
def get_task_stats(dag_id: str):
    window = _bounded_int("window", queries.DEFAULT_STATS_WINDOW, 1, MAX_WINDOW)
    stats = queries.task_stats(dag_id, window=window)
    if stats is None:
        return _dag_not_found(dag_id)
    return jsonify({"dag_id": dag_id, "window": window, "tasks": stats})


@bp.get("/dags/<dag_id>/runs/<path:run_id>/failed-tasks")
def get_failed_tasks(dag_id: str, run_id: str):
    payload = queries.failed_tasks(dag_id, run_id)
    if payload is None:
        return jsonify({"error": "run_not_found", "dag_id": dag_id, "run_id": run_id}), 404
    return jsonify(payload)


@bp.get("/sla-misses")
def get_sla_misses():
    limit = _bounded_int("limit", queries.DEFAULT_SLA_LIMIT, 1, MAX_LIMIT)
    owner = request.args.get("owner") or "all"
    return jsonify(queries.sla_misses(owner=owner, limit=limit))


@bp.get("/owners")
def get_owners():
    return jsonify({"owners": queries.list_owners()})
