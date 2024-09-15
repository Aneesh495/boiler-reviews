from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from boiler_reviews.db.models import Account, Course, Institution, Review, Term
from boiler_reviews.identity.service import register_account
from boiler_reviews.reviews.service import ReviewInput, create_review, edit_review, moderate_review, submit_review
from boiler_reviews.reviews.stats import reconcile


@dataclass(frozen=True, slots=True)
class ConcurrencyCampaign:
    workers: int
    operations_per_worker: int
    operations: int
    failures: int
    aggregate_reconciliation: dict[str, int]
    errors: tuple[str, ...]
    status: str


def run_postgres_review_campaign(factory: sessionmaker, *, workers: int = 100, operations_per_worker: int = 100) -> ConcurrencyCampaign:
    """Run independent writer transactions; intended for a disposable PostgreSQL database."""
    with factory() as session:
        institution = Institution(name="Concurrency Test", code=f"CONC{datetime.now(timezone.utc).strftime('%H%M%S%f')[-8:]}")
        session.add(institution); session.flush()
        moderator = register_account(session, email=f"moderator-{institution.code}@test.invalid", password="concurrency-test-password", display_name="Concurrency moderator", roles=["moderator"], synthetic=True)
        term = Term(institution_id=institution.id, name="Fall", year=2026, starts_on="2026-08-24", ends_on="2026-12-19")
        session.add(term); session.flush()
        identities: list[tuple[str, str]] = []
        for index in range(workers):
            account = register_account(session, email=f"writer-{institution.code}-{index}@test.invalid", password="concurrency-test-password", display_name=f"Writer {index}", synthetic=True)
            course = Course(institution_id=institution.id, stable_code=f"CW{index:03d}", canonical_title=f"Concurrency course {index}")
            session.add(course); session.flush(); identities.append((account.id, course.id))
        moderator_id, term_id = moderator.id, term.id
        session.commit()
    def worker(index: int) -> int:
        account_id, course_id = identities[index]
        review_id: str | None = None
        completed = 0
        for step in range(operations_per_worker):
            with factory() as session:
                if review_id is None:
                    review = create_review(session, actor_id=account_id, data=ReviewInput(course_id=course_id, term_id=term_id, professor="Synthetic", difficulty=3, workload_hours=4, overall=4, would_recommend=True), idempotency_key=f"concurrency:{institution.code}:{index}")
                    review_id = review.id
                else:
                    review = session.get(Review, review_id)
                    if review is None:
                        raise RuntimeError("campaign review disappeared")
                    if review.status == "draft":
                        submit_review(session, actor_id=account_id, review_id=review_id)
                    elif review.status == "submitted":
                        moderate_review(session, moderator_id=moderator_id, review_id=review_id, target="published", reason="campaign")
                    elif review.status == "published" and step % 3 == 0:
                        edit_review(session, actor_id=account_id, review_id=review_id, data=ReviewInput(course_id=course_id, term_id=term_id, professor="Synthetic", difficulty=3, workload_hours=4, overall=4 + (step % 2), would_recommend=True), expected_revision=review.current_revision)
                    elif review.status == "published":
                        moderate_review(session, moderator_id=moderator_id, review_id=review_id, target="hidden", reason="campaign")
                    elif review.status == "hidden":
                        moderate_review(session, moderator_id=moderator_id, review_id=review_id, target="published", reason="campaign")
                session.commit(); completed += 1
        return completed
    failures = 0; operations = 0; errors: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, index) for index in range(workers)]
        for future in as_completed(futures):
            try: operations += future.result()
            except Exception as error:
                failures += 1
                errors.append(f"worker {len(errors)}: {type(error).__name__}: {error}")
    with factory() as session:
        reconciliation = reconcile(session, repair=False)
    return ConcurrencyCampaign(workers, operations_per_worker, operations, failures, reconciliation, tuple(errors[:10]), "passed" if operations == workers * operations_per_worker and failures == 0 and reconciliation["mismatches"] == 0 else "failed")
