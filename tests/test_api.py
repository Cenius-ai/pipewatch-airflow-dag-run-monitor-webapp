"""Read API contract: shapes, ordering, filters and 404s."""

from __future__ import annotations


def _runs(client, dag_id="load_events_daily", limit=30):
    response = client.get(f"/api/dags/{dag_id}/runs?limit={limit}")
    assert response.status_code == 200
    return response.get_json()


def test_dags_are_sorted_with_run_counts(signed_in_client):
    body = signed_in_client.get("/api/dags").get_json()
    dags = body["dags"]
    assert [dag["dag_id"] for dag in dags] == sorted(dag["dag_id"] for dag in dags)
    for dag in dags:
        assert dag["run_count"] == 30
        assert dag["last_run_state"] in {"success", "failed", "running"}
        assert dag["sla_minutes"] > 0
        assert dag["owner"]


def test_runs_are_newest_first_with_documented_fields(signed_in_client):
    body = _runs(signed_in_client)
    runs = body["runs"]
    assert body["dag_id"] == "load_events_daily"
    assert len(runs) == 30
    logical_dates = [run["logical_date"] for run in runs]
    assert logical_dates == sorted(logical_dates, reverse=True)
    for run in runs:
        assert run["state"] in {"success", "failed", "running"}
        assert isinstance(run["duration_seconds"], int)
        assert run["logical_date"] and run["start_time"]
        if run["state"] != "running":
            assert run["end_time"]
        assert "failed_task_count" in run


def test_runs_limit_is_bounded_and_honoured(signed_in_client):
    assert len(_runs(signed_in_client, limit=5)["runs"]) == 5
    assert len(_runs(signed_in_client, limit=0)["runs"]) == 1
    assert len(_runs(signed_in_client, limit=99999)["runs"]) == 30


def test_unknown_dag_returns_404(signed_in_client):
    for path in ("/api/dags/Nope/runs", "/api/dags/Nope/task-stats"):
        response = signed_in_client.get(path)
        assert response.status_code == 404
        assert response.get_json() == {"error": "dag_not_found", "dag_id": "Nope"}


def test_task_stats_ranked_by_p95(signed_in_client):
    body = signed_in_client.get("/api/dags/load_events_daily/task-stats?window=30").get_json()
    assert body["window"] == 30
    tasks = body["tasks"]
    assert tasks, "the seeded DAG must expose task statistics"
    p95_values = [task["p95_seconds"] for task in tasks]
    assert p95_values == sorted(p95_values, reverse=True)
    for task in tasks:
        assert task["p95_seconds"] >= task["p50_seconds"]
        assert task["run_count"] > 0
        assert task["last_state"] in {"success", "failed", "running"}


def test_failed_tasks_endpoint_exposes_log_excerpts(signed_in_client):
    runs = _runs(signed_in_client)["runs"]
    failed_run = next(run for run in runs if run["failed_task_count"] > 0)
    response = signed_in_client.get(
        f"/api/dags/load_events_daily/runs/{failed_run['run_id']}/failed-tasks"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["run_id"] == failed_run["run_id"]
    assert body["failed_tasks"], "a failed run must expose its failed tasks"
    for task in body["failed_tasks"]:
        assert task["excerpt_lines"], "the excerpt is stored with the task"
        assert task["excerpt_line_count"] == len(task["excerpt_lines"])
        assert task["error_line_index"] is not None
        assert 0 <= task["error_line_index"] < len(task["excerpt_lines"])
        assert task["try_number"] >= 1


def test_unknown_run_returns_404(signed_in_client):
    response = signed_in_client.get(
        "/api/dags/load_events_daily/runs/not-a-run/failed-tasks"
    )
    assert response.status_code == 404
    assert response.get_json()["error"] == "run_not_found"


def test_sla_misses_filtered_by_owner(signed_in_client):
    body = signed_in_client.get("/api/sla-misses?owner=alice.chen").get_json()
    assert body["filters"] == {"owner": "alice.chen"}
    assert body["misses"], "alice.chen must have seeded SLA misses"
    assert all(miss["owner"] == "alice.chen" for miss in body["misses"])
    assert body["total"] >= len(body["misses"])
    assert "alice.chen" in body["owners"]
    detected = [miss["detected_at"] for miss in body["misses"]]
    assert detected == sorted(detected, reverse=True)


def test_sla_misses_all_owners_and_unknown_owner(signed_in_client):
    everything = signed_in_client.get("/api/sla-misses").get_json()
    assert everything["filters"] == {"owner": "all"}
    assert len({miss["owner"] for miss in everything["misses"]}) >= 3

    empty = signed_in_client.get("/api/sla-misses?owner=nobody").get_json()
    assert empty["misses"] == []
    assert empty["total"] == 0


def test_owners_endpoint(signed_in_client):
    owners = signed_in_client.get("/api/owners").get_json()["owners"]
    assert len(owners) >= 3
    assert owners == sorted(owners)
