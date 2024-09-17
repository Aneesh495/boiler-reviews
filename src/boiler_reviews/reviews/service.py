from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.common.errors import (
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)
from boiler_reviews.db.models import (
    AuditEvent,
    ModerationDecision,
    OutboxEvent,
    Review,
    ReviewRevision,
)
from boiler_reviews.identity.service import require_role
from boiler_reviews.reviews.stats import adjust_aggregate, remove_empty_aggregate

TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"submitted", "withdrawn"}),
    "submitted": frozenset({"draft", "published", "rejected", "withdrawn"}),
    "published": frozenset({"hidden", "withdrawn", "submitted"}),
    "hidden": frozenset({"published", "withdrawn"}),
    "rejected": frozenset({"draft", "submitted", "withdrawn"}),
    "withdrawn": frozenset(),
}


@dataclass(frozen=True, slots=True)
class ReviewInput:
    course_id: str
    term_id: str
    professor: str
    difficulty: int
    workload_hours: int
    overall: int
    would_recommend: bool
    comment: str | None = None

    def validate(self) -> None:
        errors: dict[str, str] = {}
        if not self.professor.strip():
            errors["professor"] = "required"
        if not 1 <= self.difficulty <= 5:
            errors["difficulty"] = "must be between 1 and 5"
        if self.workload_hours < 0:
            errors["workload_hours"] = "must not be negative"
        if not 1 <= self.overall <= 5:
            errors["overall"] = "must be between 1 and 5"
        if errors:
            raise ValidationError("Review fields are invalid.", fields=errors)


def _audit(session: Session, *, actor_id: str | None, event_type: str, review_id: str, payload: dict[str, object]) -> None:
    session.add(
        AuditEvent(
            actor_id=actor_id,
            event_type=event_type,
            entity_type="review",
            entity_id=review_id,
            payload_json=payload,
        )
    )


def create_review(session: Session, *, actor_id: str, data: ReviewInput, idempotency_key: str | None = None) -> Review:
    data.validate()
    if idempotency_key:
        existing = session.scalar(select(Review).where(Review.client_request_id == idempotency_key))
        if existing is not None:
            if existing.account_id != actor_id:
                raise ConflictError("The idempotency key belongs to another account.")
            return existing
    review = Review(
        account_id=actor_id,
        course_id=data.course_id,
        term_id=data.term_id,
        client_request_id=idempotency_key,
    )
    session.add(review)
    session.flush()
    session.add(
        ReviewRevision(
            review_id=review.id,
            revision=1,
            professor=data.professor.strip(),
            difficulty=data.difficulty,
            workload_hours=data.workload_hours,
            overall=data.overall,
            would_recommend=data.would_recommend,
            comment=data.comment.strip() if data.comment else None,
        )
    )
    _audit(session, actor_id=actor_id, event_type="review.created", review_id=review.id, payload={"status": review.status})
    return review


def _get_review(session: Session, review_id: str) -> Review:
    review = session.get(Review, review_id)
    if review is None:
        raise NotFoundError("Review not found.")
    return review


def _can_edit(review: Review, actor_id: str) -> None:
    if review.account_id != actor_id:
        raise PermissionDenied("Only the review owner may edit this review.")


def edit_review(session: Session, *, actor_id: str, review_id: str, data: ReviewInput, expected_revision: int) -> Review:
    data.validate()
    review = _get_review(session, review_id)
    _can_edit(review, actor_id)
    if review.current_revision != expected_revision:
        raise ConflictError("The review changed since it was loaded; refresh before editing.")
    if review.status == "withdrawn":
        raise ConflictError("Withdrawn reviews cannot be edited.")
    review.current_revision += 1
    if review.status == "published":
        review.status = "submitted"
    session.add(
        ReviewRevision(
            review_id=review.id,
            revision=review.current_revision,
            professor=data.professor.strip(),
            difficulty=data.difficulty,
            workload_hours=data.workload_hours,
            overall=data.overall,
            would_recommend=data.would_recommend,
            comment=data.comment.strip() if data.comment else None,
            submitted_at=datetime.now(UTC) if review.status == "submitted" else None,
        )
    )
    _audit(session, actor_id=actor_id, event_type="review.edited", review_id=review.id, payload={"revision": review.current_revision})
    return review


def submit_review(session: Session, *, actor_id: str, review_id: str) -> Review:
    review = _get_review(session, review_id)
    _can_edit(review, actor_id)
    _transition(session, review, actor_id=actor_id, target="submitted", reason="owner submission")
    return review


def moderate_review(
    session: Session,
    *,
    moderator_id: str,
    review_id: str,
    target: str,
    reason: str,
) -> Review:
    moderator = session.get(__import__("boiler_reviews.db.models", fromlist=["Account"]).Account, moderator_id)
    require_role(moderator, "moderator")
    review = _get_review(session, review_id)
    if target not in {"published", "hidden", "rejected"}:
        raise ValidationError("Unsupported moderation decision.")
    _transition(session, review, actor_id=moderator_id, target=target, reason=reason)
    session.add(
        ModerationDecision(
            review_id=review.id,
            revision=review.current_revision,
            moderator_id=moderator_id,
            decision=target,
            reason=reason.strip() or "No reason supplied",
        )
    )
    return review


def _revision(session: Session, review: Review, revision: int) -> ReviewRevision:
    value = session.scalar(
        select(ReviewRevision).where(ReviewRevision.review_id == review.id, ReviewRevision.revision == revision)
    )
    if value is None:
        raise AssertionError(f"missing review revision {review.id}:{revision}")
    return value


def _transition(session: Session, review: Review, *, actor_id: str, target: str, reason: str) -> None:
    if target not in TRANSITIONS.get(review.status, frozenset()):
        raise ConflictError(f"Cannot transition review from {review.status} to {target}.")
    old_status = review.status
    old_published = _revision(session, review, review.published_revision) if review.published_revision else None
    has_public_approved_revision = old_published is not None and old_status in {"published", "submitted", "rejected"}
    if target in {"hidden", "withdrawn"} and has_public_approved_revision:
        aggregate = adjust_aggregate(
            session,
            course_id=review.course_id,
            term_id=review.term_id,
            revision=old_published,
            direction=-1,
        )
        remove_empty_aggregate(session, aggregate)
    review.status = target
    if target == "published":
        new_published = _revision(session, review, review.current_revision)
        # A pending/rejected revision replaces the old approved sufficient
        # statistics. Hidden content was already removed from the aggregate.
        if old_published is not None and old_status in {"submitted", "rejected"}:
            old_aggregate = adjust_aggregate(session, course_id=review.course_id, term_id=review.term_id, revision=old_published, direction=-1)
            remove_empty_aggregate(session, old_aggregate)
            session.flush()
        adjust_aggregate(session, course_id=review.course_id, term_id=review.term_id, revision=new_published, direction=1)
        review.published_revision = review.current_revision
        new_published.submitted_at = datetime.now(UTC)
    _audit(
        session,
        actor_id=actor_id,
        event_type="review.status_changed",
        review_id=review.id,
        payload={"from": old_status, "to": target, "reason": reason},
    )
    session.add(
        OutboxEvent(
            event_key=f"review:{review.id}:transition:{uuid.uuid4()}",
            event_type="review.status_changed",
            payload_json={"review_id": review.id, "from": old_status, "to": target},
        )
    )
