from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from boiler_reviews.config import Settings


def build_engine(settings: Settings) -> Engine:
    kwargs: dict[str, Any] = {
        "future": True,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": settings.connect_timeout_seconds},
    }
    if settings.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": settings.connect_timeout_seconds,
        }
    engine = create_engine(settings.database_url, **kwargs)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_sqlite_integrity(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.close()
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
