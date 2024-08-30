from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, create_engine, inspect, insert, select, text

from boiler_reviews.config import Settings, project_root
from boiler_reviews.db.models import Base
from boiler_reviews.db.session import build_engine

MIGRATIONS = ("0001_domain_schema", "0002_task_attempts")
MIGRATION_VERSION = MIGRATIONS[-1]


def _migration_table(metadata: MetaData) -> Table:
    return Table(
        "schema_migrations",
        metadata,
        Column("version", String(120), primary_key=True),
        Column("applied_at", DateTime(timezone=True), nullable=False),
        extend_existing=True,
    )


def _apply_migration(connection, version: str) -> None:
    if version == "0001_domain_schema":
        # The first release's complete model metadata is the authored initial migration.
        Base.metadata.create_all(connection)
    elif version == "0002_task_attempts":
        columns = {column["name"] for column in inspect(connection).get_columns("durable_tasks")}
        if "attempts" not in columns:
            connection.execute(text("ALTER TABLE durable_tasks ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"))
    else:
        raise ValueError(f"unknown migration {version}")


def upgrade(engine: Engine) -> bool:
    """Apply every missing migration in order, without dropping application data."""
    migration_metadata = MetaData()
    migrations = _migration_table(migration_metadata)
    migration_metadata.create_all(engine, tables=[migrations])
    changed = False
    for version in MIGRATIONS:
        with engine.begin() as connection:
            existing = connection.execute(select(migrations.c.version).where(migrations.c.version == version)).scalar_one_or_none()
            if existing:
                continue
            _apply_migration(connection, version)
            connection.execute(insert(migrations).values(version=version, applied_at=datetime.now(timezone.utc)))
            changed = True
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply safe Boiler Reviews migrations")
    parser.add_argument("command", choices=["upgrade"])
    parser.parse_args()
    settings = Settings.from_env()
    settings.ensure_local_directories(project_root())
    engine = build_engine(settings)
    changed = upgrade(engine)
    print(f"migrations: {'applied' if changed else 'already applied'} ({', '.join(MIGRATIONS)})")


if __name__ == "__main__":
    main()
