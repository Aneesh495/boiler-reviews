from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.common.errors import ConflictError, NotFoundError
from boiler_reviews.db.models import HelpfulVote, Review, ReviewReport


def vote_helpful(session: Session, *, account_id: str, review_id: str, helpful: bool) -> HelpfulVote:
    review = session.get(Review, review_id)
    if review is None:
        raise NotFoundError("Review not found.")
    if review.account_id == account_id:
        raise ConflictError("Authors cannot vote on their own review.")
    vote = session.scalar(select(HelpfulVote).where(HelpfulVote.account_id == account_id, HelpfulVote.review_id == review_id))
    if vote is None:
        vote = HelpfulVote(account_id=account_id, review_id=review_id, helpful=helpful)
        session.add(vote)
    else:
        vote.helpful = helpful
    return vote


def report_review(session: Session, *, account_id: str, review_id: str, reason: str) -> ReviewReport:
    if session.get(Review, review_id) is None:
        raise NotFoundError("Review not found.")
    reason = reason.strip()
    if not reason:
        raise ConflictError("A moderation report needs a reason.")
    existing = session.scalar(select(ReviewReport).where(ReviewReport.account_id == account_id, ReviewReport.review_id == review_id, ReviewReport.status == "open"))
    if existing is not None:
        return existing
    report = ReviewReport(account_id=account_id, review_id=review_id, reason=reason)
    session.add(report)
    return report


def moderation_queue(session: Session) -> list[tuple[Review, int, int]]:
    """Return submitted revisions and open report counts for an operator queue."""
    rows = session.execute(
        select(Review, ReviewReport)
        .outerjoin(ReviewReport, (ReviewReport.review_id == Review.id) & (ReviewReport.status == "open"))
        .where(Review.status == "submitted")
        .order_by(Review.created_at.asc())
    ).all()
    counts: dict[str, tuple[Review, int, int]] = {}
    for review, report in rows:
        current = counts.get(review.id, (review, review.current_revision, 0))
        counts[review.id] = (current[0], current[1], current[2] + int(report is not None))
    return list(counts.values())
