from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.common.errors import ConflictError
from boiler_reviews.db.models import Review


class AppealState(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True, slots=True)
class DuplicatePolicy:
    one_account_course_term: bool = True
    allow_resubmission_after_rejection: bool = True
    explain_identity_limit: str = "The account/course/term rule limits duplicate contributions but cannot prove real-world enrollment or identity uniqueness."


def assert_review_contribution_allowed(session: Session, *, account_id: str, course_id: str, term_id: str, policy: DuplicatePolicy | None = None) -> None:
    policy = policy or DuplicatePolicy()
    if not policy.one_account_course_term:
        return
    existing = session.scalar(select(Review).where(Review.account_id == account_id, Review.course_id == course_id, Review.term_id == term_id))
    if existing is not None and not (policy.allow_resubmission_after_rejection and existing.status == "rejected"):
        raise ConflictError("This account already has a contribution for the course and term.")


def allowed_appeal_transition(source: AppealState, target: AppealState) -> bool:
    transitions = {AppealState.OPEN: {AppealState.REVIEWING, AppealState.WITHDRAWN}, AppealState.REVIEWING: {AppealState.RESOLVED, AppealState.WITHDRAWN}, AppealState.RESOLVED: set(), AppealState.WITHDRAWN: set()}
    return target in transitions[source]


def appeal_payload(*, review_id: str, state: AppealState, reason: str, actor_id: str) -> dict[str, str]:
    return {"review_id": review_id, "state": state.value, "reason": reason.strip(), "actor_id": actor_id, "recorded_at": datetime.now(UTC).isoformat()}
