"""The seeded demo dataset: demo login, idempotency and composite-key correctness."""

from __future__ import annotations

from sqlalchemy import func, select

from pipewatch import db
from pipewatch.auth import verify_password
from pipewatch.models import Dag, DagRun, SlaMiss, TaskInstance, User
from pipewatch.seed import DEMO_ACCOUNTS, seed, table_counts
from pipewatch.services import queries


def test_demo_user_is_seeded_and_verifies():
    with db.session_scope() as session:
        user = session.execute(
            select(User).where(User.username == "cenius")
        ).scalar_one_or_none()
    assert user is not None, "the demo user 'cenius' must exist"
    assert user.email == "cenius@cenius.ai"
    assert verify_password(user.password_hash, "cenius")
    assert "cenius" not in (user.password_hash or ""), "password must never be stored raw"


def test_secondary_demo_account_verifies():
    with db.session_scope() as session:
        user = session.execute(
            select(User).where(User.username == "airflow")
        ).scalar_one_or_none()
    assert user is not None
    assert verify_password(user.password_hash, "airflow-demo")


def test_seed_is_idempotent():
    before = table_counts()
    seed()
    after = table_counts()
    assert before == after
    assert after["users"] >= 2
    assert after["dags"] == 6
    assert after["runs"] == 180
    assert after["sla_misses"] > 0


def test_two_dags_share_a_run_id_under_their_own_composite_key():
    shared = (
        "scheduled__2026-01-01T00:00:00"  # any daily run id repeats across daily DAGs
    )
    with db.session_scope() as session:
        run_ids = session.execute(
            select(DagRun.run_id, func.count(func.distinct(DagRun.dag_id)))
            .group_by(DagRun.run_id)
            .having(func.count(func.distinct(DagRun.dag_id)) > 1)
            .limit(1)
        ).first()
    assert run_ids is not None, "at least one run_id must be shared by two DAGs"
    shared_run_id, dag_count = run_ids
    assert shared_run_id.startswith("scheduled__")
    assert dag_count >= 2

    with db.session_scope() as session:
        owners = session.execute(
            select(TaskInstance.dag_id)
            .where(TaskInstance.run_id == shared_run_id)
            .distinct()
        ).scalars().all()
    assert len(owners) >= 2

    # Each DAG's run only exposes its own task instances.
    for dag_id in owners:
        payload = queries.failed_tasks(dag_id, shared_run_id)
        if payload is None:
            continue
        for task in payload["failed_tasks"]:
            with db.session_scope() as session:
                row = session.execute(
                    select(TaskInstance).where(
                        TaskInstance.dag_id == dag_id,
                        TaskInstance.run_id == shared_run_id,
                        TaskInstance.task_id == task["task_id"],
                    )
                ).scalars().all()
            assert row, "failed task must belong to the requested DAG"


def test_failed_task_excerpt_metadata():
    with db.session_scope() as session:
        task = session.execute(
            select(TaskInstance)
            .where(TaskInstance.state == "failed", TaskInstance.log_truncated.is_(True))
            .limit(1)
        ).scalar_one()
        lines = task.log_excerpt.split("\n")
        assert task.total_log_lines > task.excerpt_line_count
        assert task.excerpt_line_count == len(lines)
        assert task.error_line_index is not None
        assert 0 <= task.error_line_index < len(lines)
        error_line = lines[task.error_line_index]
        assert ":" in error_line or "Error" in error_line or "timeout" in error_line


def test_sla_misses_cover_multiple_owners():
    with db.session_scope() as session:
        owners = session.execute(select(SlaMiss.owner).distinct()).scalars().all()
        total = session.execute(select(func.count()).select_from(SlaMiss)).scalar_one()
    assert total >= 10
    assert len(owners) >= 3


def test_demo_accounts_are_documented_constants():
    primary = DEMO_ACCOUNTS[0]
    assert primary["username"] == "cenius"
    assert primary["email"] == "cenius@cenius.ai"
    assert primary["role"] == "admin"


def test_every_dag_has_runs_and_task_instances():
    dags = queries.list_dags()
    assert len(dags) == 6
    for dag in dags:
        assert dag["run_count"] == 30
        stats = queries.task_stats(dag["dag_id"])
        assert stats, f"{dag['dag_id']} must expose task statistics"
        assert all(task["run_count"] > 0 for task in stats)
