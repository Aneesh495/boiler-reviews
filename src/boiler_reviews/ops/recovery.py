from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.db.models import DurableTask


def reconcile_expired_tasks(session: Session) -> dict[str, int]:
    """Make interrupted leases runnable without allowing an old worker to write."""
    now = datetime.now(UTC)
    rows = session.scalars(select(DurableTask).where(DurableTask.status == "running", DurableTask.lease_until < now)).all()
    requeued = 0
    cancelled = 0
    for task in rows:
        task.lease_owner = None
        task.lease_until = None
        if task.cancel_requested:
            task.status = "cancelled"
            cancelled += 1
        else:
            task.status = "queued"
            requeued += 1
    return {"expired": len(rows), "requeued": requeued, "cancelled": cancelled}
