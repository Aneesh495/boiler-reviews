from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, MetaData, String, Table, create_engine, insert, select

from boiler_reviews.config import Settings, project_root
from boiler_reviews.db.models import Base
from boiler_reviews.db.session import build_engine

MIGRATION_VERSION = "0001_domain_schema"


def _migration_table(metadata: MetaData) -> Table:
    return Table(
        "schema_migrations",
        metadata,
        # This table is deliberately kept small and append-only.
        __import__("sqlalchemy").Column("version", String(120), primary_key=True),
        __import__("sqlalchemy").Column("applied_at", __import__("sqlalchemy").DateTime(timezone=True), nullable=False),
        extend_existing=True,
    )


def upgrade(engine: Engine) -> bool:
    """Apply the idempotent domain migration and return whether it changed state."""
    migration_metadata = MetaData()
    migrations = _migration_table(migration_metadata)
    migration_metadata.create_all(engine, tables=[migrations])
    with engine.begin() as connection:
        existing = connection.execute(
            select(migrations.c.version).where(migrations.c.version == MIGRATION_VERSION)
        ).scalar_one_or_none()
        if existing:
            return False
        # The model metadata is the authored migration body for this first release.
        # Future changes add numbered migration functions and never drop legacy data.
        Base.metadata.create_all(connection)
        connection.execute(
            insert(migrations).values(
                version=MIGRATION_VERSION,
                applied_at=datetime.now(timezone.utc),
            )
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply safe Boiler Reviews migrations")
    parser.add_argument("command", choices=["upgrade"])
    args = parser.parse_args()
    settings = Settings.from_env()
    settings.ensure_local_directories(project_root())
    engine = build_engine(settings)
    changed = upgrade(engine)
    print(f"migration {MIGRATION_VERSION}: {'applied' if changed else 'already applied'}")


if __name__ == "__main__":
    main()
