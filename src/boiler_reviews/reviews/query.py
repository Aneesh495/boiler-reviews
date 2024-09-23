from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from boiler_reviews.db.models import Course, Review, ReviewRevision, Term


@dataclass(frozen=True, slots=True)
class ReviewFilter:
    course_id: str | None = None
    term_id: str | None = None
    professor: str | None = None
    min_overall: int | None = None
    would_recommend: bool | None = None
    cohort: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewCursor:
    created_at: datetime
    review_id: str

    def encode(self) -> str:
        return f"{self.created_at.isoformat()}|{self.review_id}"

    @classmethod
    def decode(cls, value: str | None) -> ReviewCursor | None:
        if not value:
            return None
        timestamp, separator, review_id = value.partition("|")
        if not separator:
            raise ValueError("cursor is malformed")
        return cls(datetime.fromisoformat(timestamp), review_id)


@dataclass(frozen=True, slots=True)
class ReviewPage:
    items: tuple[dict[str, Any], ...]
    next_cursor: str | None
    total: int


def _statement(filters: ReviewFilter):
    statement = select(Review, ReviewRevision, Course, Term).join(ReviewRevision, and_(ReviewRevision.review_id == Review.id, ReviewRevision.revision == Review.published_revision)).join(Course, Course.id == Review.course_id).join(Term, Term.id == Review.term_id).where(Review.status.in_(["published", "submitted", "rejected"]), Review.published_revision.is_not(None))
    if filters.course_id:
        statement = statement.where(Review.course_id == filters.course_id)
    if filters.term_id:
        statement = statement.where(Review.term_id == filters.term_id)
    if filters.professor:
        statement = statement.where(ReviewRevision.professor.ilike(f"%{filters.professor}%"))
    if filters.min_overall is not None:
        statement = statement.where(ReviewRevision.overall >= filters.min_overall)
    if filters.would_recommend is not None:
        statement = statement.where(ReviewRevision.would_recommend.is_(filters.would_recommend))
    return statement


def review_page(session: Session, *, filters: ReviewFilter | None = None, cursor: ReviewCursor | None = None, page_size: int = 25) -> ReviewPage:
    filters = filters or ReviewFilter()
    page_size = min(max(page_size, 1), 100)
    statement = _statement(filters).order_by(Review.created_at.desc(), Review.id.desc())
    if cursor:
        statement = statement.where(or_(Review.created_at < cursor.created_at, and_(Review.created_at == cursor.created_at, Review.id < cursor.review_id)))
    rows = session.execute(statement.limit(page_size + 1)).all()
    more = len(rows) > page_size
    rows = rows[:page_size]
    items = tuple({"id": review.id, "course_id": review.course_id, "course_code": course.stable_code, "term_id": review.term_id, "term": f"{term.name} {term.year}", "status": review.status, "revision": review.current_revision, "published_revision": review.published_revision, "professor": revision.professor, "difficulty": revision.difficulty, "workload_hours": revision.workload_hours, "overall": revision.overall, "would_recommend": revision.would_recommend, "comment": revision.comment, "content": {"professor": revision.professor, "difficulty": revision.difficulty, "workload_hours": revision.workload_hours, "overall": revision.overall, "would_recommend": revision.would_recommend, "comment": revision.comment}} for review, revision, course, term in rows)
    next_cursor = ReviewCursor(rows[-1][0].created_at, rows[-1][0].id).encode() if more and rows else None
    total = session.scalar(select(func.count()).select_from(_statement(filters).subquery())) or 0
    return ReviewPage(items, next_cursor, total)


def instructor_breakdown(session: Session, *, course_id: str, term_id: str | None = None) -> list[dict[str, Any]]:
    statement = select(ReviewRevision.professor, func.count(Review.id), func.avg(ReviewRevision.overall), func.avg(ReviewRevision.difficulty), func.avg(ReviewRevision.workload_hours)).join(Review, and_(ReviewRevision.review_id == Review.id, ReviewRevision.revision == Review.published_revision)).where(Review.course_id == course_id, Review.status.in_(["published", "submitted", "rejected"])).group_by(ReviewRevision.professor).order_by(ReviewRevision.professor)
    if term_id:
        statement = statement.where(Review.term_id == term_id)
    return [{"professor": professor, "review_count": count, "overall_mean": float(overall) if overall is not None else None, "difficulty_mean": float(difficulty) if difficulty is not None else None, "workload_mean_hours": float(workload) if workload is not None else None} for professor, count, overall, difficulty, workload in session.execute(statement)]


def cohort_counts(session: Session, *, course_id: str) -> list[dict[str, Any]]:
    statement = select(Term.name, Term.year, func.count(Review.id)).join(Review, Review.term_id == Term.id).where(Review.course_id == course_id, Review.status.in_(["published", "submitted", "rejected"])).group_by(Term.name, Term.year).order_by(Term.year.desc(), Term.name.asc())
    return [{"term": name, "year": year, "review_count": count} for name, year, count in session.execute(statement)]
