from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.db.models import AuditEvent, OutboxEvent


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    event_id: str
    event_type: str
    applied: bool
    duplicate: bool


def claim_projection(session: Session, *, event_id: str, owner: str) -> OutboxEvent | None:
    event = session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update())
    if event is None or event.processed_at is not None:
        return None
    if event.claimed_by not in {None, owner}:
        return None
    event.claimed_by = owner
    return event


def apply_projection(session: Session, *, event: OutboxEvent, owner: str, handlers: dict[str, Callable[[dict[str, Any]], None]]) -> ProjectionResult:
    if event.claimed_by != owner:
        return ProjectionResult(event.id, event.event_type, False, True)
    handler = handlers.get(event.event_type)
    if handler is not None:
        handler(event.payload_json)
    event.processed_at = event.updated_at
    event.claimed_until = None
    session.add(AuditEvent(actor_id=None, event_type="outbox.applied", entity_type="outbox_event", entity_id=event.id, payload_json={"event_type": event.event_type, "handler": handler is not None}))
    return ProjectionResult(event.id, event.event_type, handler is not None, False)
