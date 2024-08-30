from __future__ import annotations

import pytest
from sqlalchemy import select

from boiler_reviews.common.errors import ConflictError
from boiler_reviews.db.models import DurableTask
from boiler_reviews.tasks.outbox import claim_events
from boiler_reviews.tasks.queue import claim, enqueue, finish


def test_task_fencing_rejects_stale_worker(app):
    factory = app.config["TEST_FACTORY"]
    with factory() as session:
        task = enqueue(session, task_type="solve", payload={"seed": 1}, idempotency_key="solve:1")
        first = claim(session, owner="worker-a", lease_seconds=1)
        assert first is not None
        session.commit()
    with factory() as session:
        session.execute(__import__("sqlalchemy").update(DurableTask).where(DurableTask.id == task.id).values(lease_until=None))
        second = claim(session, owner="worker-b", lease_seconds=60)
        assert second is not None
        with pytest.raises(ConflictError):
            finish(session, lease=first, result={"stale": True})
        finish(session, lease=second, result={"ok": True})
        session.commit()
    with factory() as session:
        stored = session.scalar(select(DurableTask).where(DurableTask.id == task.id))
        assert stored is not None
        assert stored.status == "succeeded"
        assert stored.attempts == 2


def test_idempotent_task_enqueue(app):
    with app.config["TEST_FACTORY"]() as session:
        first = enqueue(session, task_type="catalog", payload={}, idempotency_key="catalog:1")
        second = enqueue(session, task_type="catalog", payload={"different": True}, idempotency_key="catalog:1")
        assert first.id == second.id


def test_outbox_claim_is_lease_based(app):
    factory = app.config["TEST_FACTORY"]
    with factory() as session:
        from boiler_reviews.db.models import OutboxEvent
        session.add(OutboxEvent(event_key="key", event_type="test", payload_json={}))
        session.commit()
    with factory() as session:
        ids = claim_events(session, owner="worker", limit=1)
        assert len(ids) == 1
        session.commit()
