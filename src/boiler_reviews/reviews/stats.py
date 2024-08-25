from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from boiler_reviews.db.models import CourseAggregate, Review, ReviewRevision


@dataclass(frozen=True, slots=True)
class RatingSummary:
    count: int
    mean: float | None
    lower: float | None
    upper: float | None
    warning: str | None


def adjust_aggregate(
    session: Session,
    *,
    course_id: str,
    term_id: str,
    revision: ReviewRevision,
    direction: int,
) -> CourseAggregate:
    """Apply one published revision delta; caller owns the surrounding transaction."""
    aggregate = session.scalar(
        select(CourseAggregate)
        .where(CourseAggregate.course_id == course_id, CourseAggregate.term_id == term_id)
        .with_for_update()
    )
    if aggregate is None:
        aggregate = CourseAggregate(course_id=course_id, term_id=term_id)
        session.add(aggregate)
        session.flush()
    aggregate.review_count += direction
    aggregate.sum_overall += direction * revision.overall
    aggregate.sum_difficulty += direction * revision.difficulty
    aggregate.sum_workload += direction * revision.workload_hours
    aggregate.recommend_count += direction * int(revision.would_recommend)
    aggregate.revision += 1
    if aggregate.review_count < 0:
        raise AssertionError("published aggregate count cannot be negative")
    return aggregate


def remove_empty_aggregate(session: Session, aggregate: CourseAggregate) -> None:
    if aggregate.review_count == 0:
        session.delete(aggregate)


def full_recompute(session: Session) -> dict[tuple[str, str], dict[str, int]]:
    """Authoritative scan of published revisions, used only by repair/reconciliation."""
    values: dict[tuple[str, str], dict[str, int]] = {}
    rows = session.execute(
        select(Review, ReviewRevision)
        .join(ReviewRevision, (ReviewRevision.review_id == Review.id) & (ReviewRevision.revision == Review.published_revision))
        .where(Review.status == "published")
    )
    for review, revision in rows:
        key = (review.course_id, review.term_id)
        current = values.setdefault(
            key,
            {"review_count": 0, "sum_overall": 0, "sum_difficulty": 0, "sum_workload": 0, "recommend_count": 0},
        )
        current["review_count"] += 1
        current["sum_overall"] += revision.overall
        current["sum_difficulty"] += revision.difficulty
        current["sum_workload"] += revision.workload_hours
        current["recommend_count"] += int(revision.would_recommend)
    return values


def reconcile(session: Session, *, repair: bool = False) -> dict[str, int]:
    expected = full_recompute(session)
    actual_rows = session.scalars(select(CourseAggregate)).all()
    actual = {
        (row.course_id, row.term_id): {
            "review_count": row.review_count,
            "sum_overall": row.sum_overall,
            "sum_difficulty": row.sum_difficulty,
            "sum_workload": row.sum_workload,
            "recommend_count": row.recommend_count,
        }
        for row in actual_rows
    }
    mismatches = 0
    repaired = 0
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key, {"review_count": 0}) != actual.get(key, {"review_count": 0}):
            mismatches += 1
            if repair:
                row = next((r for r in actual_rows if (r.course_id, r.term_id) == key), None)
                if key not in expected:
                    if row is not None:
                        session.delete(row)
                elif row is None:
                    session.add(CourseAggregate(course_id=key[0], term_id=key[1], **expected[key], revision=1))
                else:
                    for name, value in expected[key].items():
                        setattr(row, name, value)
                    row.revision += 1
                repaired += 1
    return {"groups_checked": len(set(expected) | set(actual)), "mismatches": mismatches, "repaired": repaired}


def rating_summary(count: int, total: int, *, prior_mean: float = 3.5, prior_strength: int = 8) -> RatingSummary:
    if count == 0:
        return RatingSummary(0, None, None, None, "No published review evidence")
    mean = (total + prior_strength * prior_mean) / (count + prior_strength)
    # Wilson-style uncertainty around a normalized 1..5 rating. This is an
    # explicit decision aid, not a claim of a population-level difference.
    variance = 1.0 / max(count + prior_strength, 1)
    margin = 1.96 * math.sqrt(variance)
    return RatingSummary(count, mean, max(1.0, mean - margin), min(5.0, mean + margin), None if count >= 8 else "Small sample")
