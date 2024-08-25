from __future__ import annotations

import pytest

from boiler_reviews.config import Settings
from boiler_reviews.db.migrate import upgrade
from boiler_reviews.db.models import Course, Institution, Term
from boiler_reviews.db.session import build_engine, build_session_factory, session_scope
from boiler_reviews.web.app import create_app


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        environment="test",
        secret_key="test-secret-key-for-suite",
        database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        csrf_enabled=False,
    )
    engine = build_engine(settings)
    upgrade(engine)
    factory = build_session_factory(engine)
    with session_scope(factory) as session:
        institution = Institution(name="Test University", code="TEST")
        session.add(institution)
        session.flush()
        course = Course(institution_id=institution.id, stable_code="CS101", canonical_title="Foundations")
        term = Term(institution_id=institution.id, name="Fall", year=2026, starts_on="2026-08-24", ends_on="2026-12-19")
        session.add_all([course, term])
        session.flush()
        app = create_app(settings)
        app.config.update(TESTING=True, TEST_COURSE_ID=course.id, TEST_TERM_ID=term.id, TEST_FACTORY=factory)
    yield app
    engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()
