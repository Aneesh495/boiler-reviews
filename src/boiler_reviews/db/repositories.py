from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from boiler_reviews.db.models import Course, CourseAggregate, CourseVersion, Review, ReviewRevision


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: tuple[T, ...]
    page: int
    page_size: int
    total: int

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total


def paginate[T](session: Session, statement: Select[tuple[T]], *, page: int, page_size: int) -> Page[T]:
    bounded_page = max(1, page)
    bounded_size = min(max(1, page_size), 100)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = tuple(session.scalars(statement.offset((bounded_page - 1) * bounded_size).limit(bounded_size)).all())
    return Page(items, bounded_page, bounded_size, total)


class CourseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str = "", *, page: int = 1, page_size: int = 25) -> Page[Course]:
        statement = select(Course).order_by(Course.stable_code.asc())
        if query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(Course.stable_code.ilike(pattern) | Course.canonical_title.ilike(pattern))
        return paginate(self.session, statement, page=page, page_size=page_size)

    def evidence(self, course_id: str) -> dict[str, Any]:
        rows = self.session.scalars(select(CourseAggregate).where(CourseAggregate.course_id == course_id).order_by(CourseAggregate.term_id)).all()
        count = sum(row.review_count for row in rows)
        return {"review_count": count, "overall_mean": sum(row.sum_overall for row in rows) / count if count else None, "difficulty_mean": sum(row.sum_difficulty for row in rows) / count if count else None, "workload_mean_hours": sum(row.sum_workload for row in rows) / count if count else None, "missing": count == 0}


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def published(self, *, page: int = 1, page_size: int = 25) -> Page[tuple[Review, ReviewRevision]]:
        statement = select(Review, ReviewRevision).join(ReviewRevision, (ReviewRevision.review_id == Review.id) & (ReviewRevision.revision == Review.published_revision)).where(Review.status.in_(['published', 'submitted', 'rejected']), Review.published_revision.is_not(None)).order_by(Review.created_at.desc(), Review.id.desc())
        bounded_page = max(1, page); bounded_size = min(max(1, page_size), 100); total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        items = tuple(self.session.execute(statement.offset((bounded_page - 1) * bounded_size).limit(bounded_size)).all())
        return Page(items, bounded_page, bounded_size, total)


class CourseVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def for_snapshot(self, snapshot_id: str) -> tuple[CourseVersion, ...]:
        return tuple(self.session.scalars(select(CourseVersion).where(CourseVersion.snapshot_id == snapshot_id).order_by(CourseVersion.code)).all())
