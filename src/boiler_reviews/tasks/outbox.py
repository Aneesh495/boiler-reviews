from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from boiler_reviews.common.errors import ConflictError
from boiler_reviews.db.models import OutboxEvent


def claim_events(session: Session, *, owner: str, limit: int = 50, lease_seconds: int = 60) -> list[str]:
    now = datetime.now(UTC)
    rows = session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.processed_at.is_(None), or_(OutboxEvent.claimed_until.is_(None), OutboxEvent.claimed_until < now))
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    ids: list[str] = []
    for row in rows:
        row.claimed_by = owner
        row.claimed_until = now + timedelta(seconds=lease_seconds)
        row.attempts += 1
        ids.append(row.id)
    return ids


def process_events(factory: sessionmaker[Session], *, owner: str, handler: Callable[[str, dict[str, Any]], None], limit: int = 50) -> int:
    with factory() as session:
        ids = claim_events(session, owner=owner, limit=limit)
        session.commit()
    processed = 0
    for event_id in ids:
        with factory() as session:
            event = session.get(OutboxEvent, event_id)
            if event is None or event.processed_at is not None:
                session.rollback()
                continue
            if event.claimed_by != owner:
                raise ConflictError("Outbox claim was fenced by another worker.")
            handler(event.event_type, event.payload_json)
            event.processed_at = datetime.now(UTC)
            event.claimed_until = None
            session.commit()
            processed += 1
    return processed
