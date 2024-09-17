from __future__ import annotations

from sqlalchemy import Table, inspect, select

from boiler_reviews.db.migrate import MIGRATIONS, upgrade
from boiler_reviews.db.models import Base


def test_migration_is_idempotent(app):
    engine = app.config["ENGINE"]
    assert upgrade(engine) is False
    tables = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables).issubset(tables)
    with engine.connect() as connection:
        migrations = Table("schema_migrations", Base.metadata, autoload_with=engine)
        versions = connection.execute(select(migrations.c.version)).scalars().all()
    assert versions == list(MIGRATIONS)
