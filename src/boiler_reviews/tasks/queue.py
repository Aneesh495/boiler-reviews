from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from boiler_reviews.common.errors import ConflictError, NotFoundError
from boiler_reviews.db.models import DurableTask


@dataclass(frozen=True, slots=True)
class TaskLease:
    task_id: str
    owner: str
    fencing_token: int


def enqueue(session: Session, *, task_type: str, payload: dict[str, Any], account_id: str | None = None, idempotency_key: str | None = None) -> DurableTask:
    if idempotency_key:
        existing = session.scalar(select(DurableTask).where(DurableTask.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    task = DurableTask(task_type=task_type, payload_json=payload, account_id=account_id, idempotency_key=idempotency_key)
    session.add(task)
    session.flush()
    return task


def claim(session: Session, *, owner: str, lease_seconds: int = 60) -> TaskLease | None:
    now = datetime.now(timezone.utc)
    task = session.scalar(
        select(DurableTask)
        .where(
            or_(DurableTask.status == "queued", DurableTask.status == "running"),
            or_(DurableTask.lease_until.is_(None), DurableTask.lease_until < now),
            DurableTask.cancel_requested.is_(False),
        )
        .order_by(DurableTask.created_at.asc())
        .with_for_update(skip_locked=True)
    )
    if task is None:
        return None
    task.status = "running"
    task.lease_owner = owner
    task.lease_until = now + timedelta(seconds=lease_seconds)
    task.fencing_token += 1
    task.attempts = getattr(task, "attempts", 0) + 1
    session.flush()
    return TaskLease(task.id, owner, task.fencing_token)


def _owned(session: Session, lease: TaskLease) -> DurableTask:
    task = session.get(DurableTask, lease.task_id)
    if task is None:
        raise NotFoundError("Task not found.")
    if task.lease_owner != lease.owner or task.fencing_token != lease.fencing_token or task.status != "running":
        raise ConflictError("Task lease is stale; refusing a fenced write.")
    return task


def heartbeat(session: Session, *, lease: TaskLease, lease_seconds: int = 60) -> DurableTask:
    task = _owned(session, lease)
    if task.cancel_requested:
        task.status = "cancelled"
        raise ConflictError("Task cancellation was requested.")
    task.lease_until = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
    return task


def progress(session: Session, *, lease: TaskLease, value: int) -> DurableTask:
    task = _owned(session, lease)
    task.progress = max(0, min(100, value))
    return task


def finish(session: Session, *, lease: TaskLease, result: dict[str, Any]) -> DurableTask:
    task = _owned(session, lease)
    if task.cancel_requested:
        task.status = "cancelled"
    else:
        task.status = "succeeded"
        task.progress = 100
        task.result_json = result
    task.lease_until = None
    return task


def fail(session: Session, *, lease: TaskLease, error: dict[str, Any]) -> DurableTask:
    task = _owned(session, lease)
    task.status = "failed" if not task.cancel_requested else "cancelled"
    task.error_json = error
    task.lease_until = None
    return task


def request_cancel(session: Session, *, task_id: str, account_id: str | None) -> DurableTask:
    task = session.get(DurableTask, task_id)
    if task is None:
        raise NotFoundError("Task not found.")
    if task.account_id is not None and task.account_id != account_id:
        raise ConflictError("Only the task owner may cancel this task.")
    if task.status in {"succeeded", "failed", "cancelled"}:
        return task
    task.cancel_requested = True
    return task


class TaskWorker:
    def __init__(self, factory: sessionmaker[Session], handlers: dict[str, Callable[[Session, DurableTask, TaskLease], dict[str, Any]]], *, owner: str, lease_seconds: int = 60) -> None:
        self.factory = factory
        self.handlers = handlers
        self.owner = owner
        self.lease_seconds = lease_seconds

    def run_once(self) -> bool:
        with self.factory() as session:
            lease = claim(session, owner=self.owner, lease_seconds=self.lease_seconds)
            if lease is None:
                session.rollback()
                return False
            task = session.get(DurableTask, lease.task_id)
            session.commit()
        if task is None:
            return False
        handler = self.handlers.get(task.task_type)
        if handler is None:
            with self.factory() as session:
                fail(session, lease=lease, error={"code": "unknown_task_type", "task_type": task.task_type})
                session.commit()
            return True
        try:
            with self.factory() as session:
                current = session.get(DurableTask, lease.task_id)
                if current is None:
                    return False
                result = handler(session, current, lease)
                finish(session, lease=lease, result=result)
                session.commit()
        except Exception as error:
            with self.factory() as session:
                try:
                    fail(session, lease=lease, error={"type": type(error).__name__, "message": str(error)})
                    session.commit()
                except ConflictError:
                    session.rollback()
            raise
        return True
