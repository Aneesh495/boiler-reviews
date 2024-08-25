from __future__ import annotations

from pathlib import Path

from boiler_reviews.db.legacy import inspect_legacy


def test_legacy_report_preserves_unknown_authorship():
    report = inspect_legacy(Path(".runtime/backups/course_reviews-2026-10-01.sqlite"))
    assert report.rows["courses"] == 4
    assert report.rows["reviews"] == 12
    assert report.unknown_authorship == 12
    assert report.invalid_ratings == 0
    assert report.missing_foreign_keys == 0
