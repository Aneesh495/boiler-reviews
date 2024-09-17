from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.db.models import (
    Account,
    Course,
    Institution,
    Review,
    ReviewRevision,
    Term,
)


@dataclass(frozen=True, slots=True)
class LegacyReport:
    source: str
    rows: dict[str, int]
    invalid_ratings: int
    missing_foreign_keys: int
    unknown_authorship: int
    aggregate_mismatches: int
    course_identity_mappings: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "rows": self.rows,
            "invalid_ratings": self.invalid_ratings,
            "missing_foreign_keys": self.missing_foreign_keys,
            "unknown_authorship": self.unknown_authorship,
            "aggregate_mismatches": self.aggregate_mismatches,
            "course_identity_mappings": self.course_identity_mappings,
        }


def inspect_legacy(path: Path) -> LegacyReport:
    """Inspect the original SQLite schema without writing to either database."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        required = {"courses", "semesters", "reviews", "course_stats"}
        if not required.issubset(tables):
            raise ValueError(f"legacy database missing tables: {sorted(required - tables)}")
        rows = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in sorted(required)
        }
        invalid_ratings = int(
            conn.execute(
                """SELECT COUNT(*) FROM reviews
                   WHERE difficulty_rating NOT BETWEEN 1 AND 5
                      OR overall_rating NOT BETWEEN 1 AND 5
                      OR workload_hours < 0
                      OR would_recommend NOT IN (0, 1)"""
            ).fetchone()[0]
        )
        missing_foreign_keys = int(
            conn.execute(
                """SELECT COUNT(*) FROM reviews r
                   LEFT JOIN courses c ON c.id = r.course_id
                   LEFT JOIN semesters s ON s.id = r.semester_id
                   WHERE c.id IS NULL OR s.id IS NULL"""
            ).fetchone()[0]
        )
        mappings = {
            row["course_code"]: hashlib.sha256(row["course_code"].encode()).hexdigest()[:16]
            for row in conn.execute("SELECT course_code FROM courses ORDER BY course_code")
        }
        return LegacyReport(
            source=str(path),
            rows=rows,
            invalid_ratings=invalid_ratings,
            missing_foreign_keys=missing_foreign_keys,
            unknown_authorship=rows["reviews"],
            aggregate_mismatches=0,
            course_identity_mappings=mappings,
        )
    finally:
        conn.close()


def import_legacy(path: Path, session: Session, *, dry_run: bool = True) -> LegacyReport:
    """Import valid legacy rows, preserving unknown authorship explicitly."""
    report = inspect_legacy(path)
    if dry_run:
        return report
    if report.invalid_ratings or report.missing_foreign_keys:
        raise ValueError("legacy data failed validation; refusing partial import")

    institution = session.scalar(select(Institution).where(Institution.code == "LEGACY"))
    if institution is None:
        institution = Institution(name="Legacy institution", code="LEGACY", timezone="America/Indiana/Indianapolis")
        session.add(institution)
        session.flush()
    unknown = session.scalar(select(Account).where(Account.email == "unknown@legacy.invalid"))
    if unknown is None:
        unknown = Account(
            email="unknown@legacy.invalid",
            password_hash="!legacy-authorship-unknown!",
            display_name="Unknown legacy author",
            synthetic=True,
            is_active=False,
            roles_json=[],
        )
        session.add(unknown)
        session.flush()

    legacy = sqlite3.connect(path)
    legacy.row_factory = sqlite3.Row
    try:
        course_ids: dict[int, str] = {}
        for row in legacy.execute("SELECT id, course_code, course_name FROM courses ORDER BY id"):
            course = session.scalar(
                select(Course).where(Course.institution_id == institution.id, Course.stable_code == row["course_code"])
            )
            if course is None:
                course = Course(
                    institution_id=institution.id,
                    stable_code=row["course_code"],
                    canonical_title=row["course_name"],
                )
                session.add(course)
                session.flush()
            course_ids[int(row["id"])] = course.id
        term_ids: dict[int, str] = {}
        for row in legacy.execute("SELECT id, term, year FROM semesters ORDER BY id"):
            term = session.scalar(
                select(Term).where(
                    Term.institution_id == institution.id,
                    Term.name == row["term"],
                    Term.year == row["year"],
                )
            )
            if term is None:
                term = Term(
                    institution_id=institution.id,
                    name=row["term"],
                    year=int(row["year"]),
                    starts_on=f"{int(row['year']):04d}-01-01",
                    ends_on=f"{int(row['year']):04d}-12-31",
                )
                session.add(term)
                session.flush()
            term_ids[int(row["id"])] = term.id
        for row in legacy.execute("SELECT * FROM reviews ORDER BY id"):
            exists = session.scalar(select(Review).where(Review.client_request_id == f"legacy:{row['id']}"))
            if exists is not None:
                continue
            review = Review(
                account_id=unknown.id,
                course_id=course_ids[int(row["course_id"])],
                term_id=term_ids[int(row["semester_id"])],
                status="published",
                client_request_id=f"legacy:{row['id']}",
            )
            session.add(review)
            session.flush()
            session.add(
                ReviewRevision(
                    review_id=review.id,
                    revision=1,
                    professor=row["professor"],
                    difficulty=int(row["difficulty_rating"]),
                    workload_hours=int(row["workload_hours"]),
                    overall=int(row["overall_rating"]),
                    would_recommend=bool(row["would_recommend"]),
                    comment=row["comment"],
                )
            )
            review.published_revision = 1
        session.flush()
        return report
    finally:
        legacy.close()
