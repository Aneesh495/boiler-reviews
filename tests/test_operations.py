from __future__ import annotations

import json
import logging
from datetime import UTC

from boiler_reviews.db.models import DurableTask
from boiler_reviews.ops.logging import Metrics, RedactingJsonFormatter
from boiler_reviews.ops.recovery import reconcile_expired_tasks
from boiler_reviews.tasks.queue import enqueue


def test_redacting_formatter_omits_sensitive_fields():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "request", (), None)
    record.request_id = "req-1"
    record.password = "secret"
    encoded = RedactingJsonFormatter().format(record)
    data = json.loads(encoded)
    assert data["request_id"] == "req-1"
    assert "password" not in data


def test_metrics_snapshot_has_percentile_shape():
    metrics = Metrics(); metrics.observe("query", 4); metrics.observe("query", 8)
    assert metrics.snapshot()["timings_ms"]["query"]["p50"] == 8


def test_expired_task_is_requeued(app):
    factory = app.config["TEST_FACTORY"]
    with factory() as session:
        task = enqueue(session, task_type="solve", payload={})
        task.status = "running"
        from datetime import datetime, timedelta
        task.lease_until = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    with factory() as session:
        result = reconcile_expired_tasks(session)
        assert result["requeued"] == 1
        session.commit()
    with factory() as session:
        assert session.get(DurableTask, task.id).status == "queued"
