from __future__ import annotations

import sqlite3
from contextlib import closing

from boiler_reviews.db.legacy import inspect_legacy


def test_legacy_report_preserves_unknown_authorship(tmp_path):
    database = tmp_path / "legacy.sqlite"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript("""
            CREATE TABLE courses (id INTEGER PRIMARY KEY, course_code TEXT NOT NULL);
            CREATE TABLE semesters (id INTEGER PRIMARY KEY);
            CREATE TABLE reviews (
                course_id INTEGER, semester_id INTEGER, difficulty_rating INTEGER,
                overall_rating INTEGER, workload_hours INTEGER, would_recommend INTEGER
            );
            CREATE TABLE course_stats (course_id INTEGER);
            INSERT INTO courses VALUES (1, 'TEST101'), (2, 'TEST102'), (3, 'TEST103'), (4, 'TEST104');
            INSERT INTO semesters VALUES (1), (2), (3);
            INSERT INTO reviews
                SELECT courses.id, semesters.id, 3, 4, 5, 1 FROM courses CROSS JOIN semesters;
        """)

    report = inspect_legacy(database)
    assert report.rows["courses"] == 4
    assert report.rows["reviews"] == 12
    assert report.unknown_authorship == 12
    assert report.invalid_ratings == 0
    assert report.missing_foreign_keys == 0
