from __future__ import annotations

from sqlalchemy.orm import Session

from boiler_reviews.db.models import AuditEvent
from boiler_reviews.reviews.stats import reconcile


def reconcile_and_record(session: Session, *, actor_id: str | None, repair: bool) -> dict[str, int]:
    result = reconcile(session, repair=repair)
    if result["mismatches"]:
        session.add(
            AuditEvent(
                actor_id=actor_id,
                event_type="course_aggregates.reconciled",
                entity_type="course_aggregate",
                entity_id="all",
                payload_json={**result, "repair": repair},
            )
        )
    return result
