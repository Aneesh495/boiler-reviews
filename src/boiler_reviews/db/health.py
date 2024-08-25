from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def readiness(session: Session) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        return {"status": "not_ready", "database": "unavailable"}
    return {"status": "ready", "database": "ok"}
