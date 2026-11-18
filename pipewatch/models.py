"""SQLAlchemy models for the Pipewatch read-only Airflow mirror.

Design notes:
* `DagRun` has a composite primary key `(dag_id, run_id)` because Airflow run ids
  are only unique *per DAG* (`scheduled__2024-05-30T00:00:00` repeats across DAGs).
* `TaskInstance` and `SlaMiss` carry `(dag_id, run_id)` and reference the run
  through a composite foreign key so a task can never attach to another DAG's run.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(120), nullable=False)
    role = Column(String(32), nullable=False, default="operator")
    created_at = Column(DateTime, nullable=False)


class Dag(Base):
    __tablename__ = "dags"

    dag_id = Column(String(128), primary_key=True)
    owner = Column(String(64), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    schedule_interval = Column(String(64), nullable=False)
    sla_minutes = Column(Integer, nullable=False)

    runs = relationship("DagRun", back_populates="dag", cascade="all, delete-orphan")


class DagRun(Base):
    __tablename__ = "dag_runs"

    dag_id = Column(String(128), ForeignKey("dags.dag_id", ondelete="CASCADE"), primary_key=True)
    run_id = Column(String(128), primary_key=True)
    logical_date = Column(DateTime, nullable=False, index=True)
    state = Column(String(16), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer, nullable=False)
    sla_met = Column(Boolean, nullable=False, default=True)

    dag = relationship("Dag", back_populates="runs")
    task_instances = relationship(
        "TaskInstance", back_populates="run", cascade="all, delete-orphan"
    )
    sla_misses = relationship("SlaMiss", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_dag_runs_dag_logical", "dag_id", "logical_date"),)


class TaskInstance(Base):
    __tablename__ = "task_instances"

    id = Column(Integer, primary_key=True)
    dag_id = Column(String(128), nullable=False)
    run_id = Column(String(128), nullable=False)
    task_id = Column(String(128), nullable=False, index=True)
    state = Column(String(16), nullable=False)
    try_number = Column(Integer, nullable=False, default=1)
    duration_seconds = Column(Integer, nullable=False)
    log_excerpt = Column(Text, nullable=False, default="")
    log_truncated = Column(Boolean, nullable=False, default=False)
    total_log_lines = Column(Integer, nullable=False, default=0)
    excerpt_line_count = Column(Integer, nullable=False, default=0)
    error_line_index = Column(Integer)

    run = relationship("DagRun", back_populates="task_instances")

    __table_args__ = (
        ForeignKeyConstraint(
            ["dag_id", "run_id"],
            ["dag_runs.dag_id", "dag_runs.run_id"],
            ondelete="CASCADE",
        ),
        Index("ix_task_instances_run", "dag_id", "run_id"),
    )


class SlaMiss(Base):
    __tablename__ = "sla_misses"

    id = Column(Integer, primary_key=True)
    dag_id = Column(String(128), nullable=False)
    run_id = Column(String(128), nullable=False)
    task_id = Column(String(128))
    owner = Column(String(64), nullable=False, index=True)
    sla_threshold_seconds = Column(Integer, nullable=False)
    missed_by_seconds = Column(Integer, nullable=False)
    detected_at = Column(DateTime, nullable=False, index=True)

    run = relationship("DagRun", back_populates="sla_misses")

    __table_args__ = (
        ForeignKeyConstraint(
            ["dag_id", "run_id"],
            ["dag_runs.dag_id", "dag_runs.run_id"],
            ondelete="CASCADE",
        ),
        Index("ix_sla_misses_owner_detected", "owner", "detected_at"),
    )
