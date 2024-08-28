from __future__ import annotations

from boiler_reviews.catalog.service import activate_catalog, stage_catalog
from boiler_reviews.db.models import CatalogSnapshot


def catalog_payload(version: str = "2026.1"):
    return {
        "schema_version": "1",
        "institution_code": "CAT",
        "institution_name": "Catalog Test",
        "version": version,
        "source_uri": "fixture://catalog",
        "provenance": {"kind": "test", "synthetic": True},
        "courses": [
            {"code": "CS101", "title": "Foundations", "credits": 3, "prerequisites": "NONE"},
            {"code": "CS201", "title": "Data Structures", "credits": 3, "prerequisites": "CS101"},
        ],
        "terms": [{"name": "Fall", "year": 2026, "starts_on": "2026-08-24", "ends_on": "2026-12-19"}],
    }


def test_stage_and_activate_is_atomic_and_idempotent(app):
    factory = app.config["TEST_FACTORY"]
    with factory() as session:
        snapshot, validation = stage_catalog(session, payload=catalog_payload())
        assert validation.valid
        snapshot_id = snapshot.id
        activate_catalog(session, snapshot_id=snapshot_id)
        session.commit()
    with factory() as session:
        assert session.scalar(__import__("sqlalchemy").select(CatalogSnapshot).where(CatalogSnapshot.status == "active")).id == snapshot_id
        staged_again, _ = stage_catalog(session, payload=catalog_payload())
        assert staged_again.id == snapshot_id
        session.rollback()


def test_bad_reference_does_not_create_snapshot(app):
    payload = catalog_payload()
    payload["courses"][1]["prerequisites"] = "MISSING999"
    with app.config["TEST_FACTORY"]() as session:
        try:
            stage_catalog(session, payload=payload)
        except Exception as error:
            assert "semantic" in str(error)
        else:
            raise AssertionError("invalid catalog unexpectedly staged")
        assert session.scalar(__import__("sqlalchemy").select(CatalogSnapshot)) is None
