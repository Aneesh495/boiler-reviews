from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Institution(Timestamped, Base):
    __tablename__ = "institutions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Indiana/Indianapolis")


class Account(Timestamped, Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    roles_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class CatalogSnapshot(Timestamped, Base):
    __tablename__ = "catalog_snapshots"
    __table_args__ = (UniqueConstraint("institution_id", "version", name="uq_catalog_institution_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="staged")
    source_uri: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Course(Timestamped, Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("institution_id", "stable_code", name="uq_course_stable_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    stable_code: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_title: Mapped[str] = mapped_column(String(240), nullable=False)
    cross_list_group: Mapped[str | None] = mapped_column(String(80))


class CourseVersion(Timestamped, Base):
    __tablename__ = "course_versions"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "code", name="uq_course_version_snapshot_code"),
        CheckConstraint("credit_units > 0", name="ck_course_version_positive_credits"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("catalog_snapshots.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    credit_units: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    prerequisite_text: Mapped[str | None] = mapped_column(Text)
    prerequisite_ast: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    prerequisite_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unparsed")
    availability_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class Instructor(Timestamped, Base):
    __tablename__ = "instructors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)


class Term(Timestamped, Base):
    __tablename__ = "terms"
    __table_args__ = (UniqueConstraint("institution_id", "name", "year", name="uq_term_institution_name_year"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[str] = mapped_column(String(10), nullable=False)
    ends_on: Mapped[str] = mapped_column(String(10), nullable=False)


class Offering(Timestamped, Base):
    __tablename__ = "offerings"
    __table_args__ = (UniqueConstraint("course_version_id", "term_id", name="uq_offering_course_term"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_version_id: Mapped[str] = mapped_column(ForeignKey("course_versions.id"), nullable=False)
    term_id: Mapped[str] = mapped_column(ForeignKey("terms.id"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Section(Timestamped, Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("offering_id", "section_code", name="uq_section_offering_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    offering_id: Mapped[str] = mapped_column(ForeignKey("offerings.id"), nullable=False)
    section_code: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="lecture")
    capacity: Mapped[int | None] = mapped_column(Integer)
    capacity_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    linked_group: Mapped[str | None] = mapped_column(String(80))
    asynchronous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MeetingInterval(Timestamped, Base):
    __tablename__ = "meeting_intervals"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_meeting_weekday"),
        CheckConstraint("start_minute >= 0 AND start_minute < 1440", name="ck_meeting_start"),
        CheckConstraint("end_minute > start_minute AND end_minute <= 1440", name="ck_meeting_end"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    section_id: Mapped[str] = mapped_column(ForeignKey("sections.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PrerequisiteRecord(Timestamped, Base):
    __tablename__ = "prerequisite_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_version_id: Mapped[str] = mapped_column(ForeignKey("course_versions.id"), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    ast_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    diagnostics_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class DegreeRuleVersion(Timestamped, Base):
    __tablename__ = "degree_rule_versions"
    __table_args__ = (UniqueConstraint("institution_id", "program_code", "version", name="uq_degree_rules_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    program_code: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class StudentPlan(Timestamped, Base):
    __tablename__ = "student_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    catalog_snapshot_id: Mapped[str] = mapped_column(ForeignKey("catalog_snapshots.id"), nullable=False)
    degree_rule_version_id: Mapped[str | None] = mapped_column(ForeignKey("degree_rule_versions.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    assumptions_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class PlanItem(Timestamped, Base):
    __tablename__ = "plan_items"
    __table_args__ = (UniqueConstraint("plan_id", "course_version_id", name="uq_plan_course"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("student_plans.id"), nullable=False)
    course_version_id: Mapped[str] = mapped_column(ForeignKey("course_versions.id"), nullable=False)
    term_id: Mapped[str | None] = mapped_column(ForeignKey("terms.id"))
    section_id: Mapped[str | None] = mapped_column(ForeignKey("sections.id"))
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allocation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class CompletedCourse(Timestamped, Base):
    __tablename__ = "completed_courses"
    __table_args__ = (UniqueConstraint("account_id", "course_id", name="uq_completed_account_course"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(5))
    grade_points_milli: Mapped[int | None] = mapped_column(Integer)
    credit_units: Mapped[int] = mapped_column(Integer, nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    assumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Review(Timestamped, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("account_id", "course_id", "term_id", name="uq_review_account_course_term"),
        CheckConstraint("status IN ('draft','submitted','published','hidden','rejected','withdrawn')", name="ck_review_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False)
    term_id: Mapped[str] = mapped_column(ForeignKey("terms.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_revision: Mapped[int | None] = mapped_column(Integer)
    client_request_id: Mapped[str | None] = mapped_column(String(80), unique=True)


class ReviewRevision(Timestamped, Base):
    __tablename__ = "review_revisions"
    __table_args__ = (
        UniqueConstraint("review_id", "revision", name="uq_review_revision"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_revision_difficulty"),
        CheckConstraint("overall BETWEEN 1 AND 5", name="ck_revision_overall"),
        CheckConstraint("workload_hours >= 0", name="ck_revision_workload"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    professor: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    workload_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    would_recommend: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModerationDecision(Timestamped, Base):
    __tablename__ = "moderation_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    moderator_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class CourseAggregate(Timestamped, Base):
    __tablename__ = "course_aggregates"
    __table_args__ = (UniqueConstraint("course_id", "term_id", name="uq_aggregate_course_term"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False)
    term_id: Mapped[str] = mapped_column(ForeignKey("terms.id"), nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sum_overall: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sum_difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sum_workload: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HelpfulVote(Timestamped, Base):
    __tablename__ = "helpful_votes"
    __table_args__ = (UniqueConstraint("account_id", "review_id", name="uq_helpful_vote"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), nullable=False)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ReviewReport(Timestamped, Base):
    __tablename__ = "review_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")


class OutboxEvent(Timestamped, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("event_key", name="uq_outbox_event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_key: Mapped[str] = mapped_column(String(180), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    claimed_by: Mapped[str | None] = mapped_column(String(120))
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DurableTask(Timestamped, Base):
    __tablename__ = "durable_tasks"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_task_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(180), unique=True)


class AuditEvent(Timestamped, Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


Index("ix_course_versions_snapshot_code", CourseVersion.snapshot_id, CourseVersion.code)
Index("ix_reviews_status_course_term", Review.status, Review.course_id, Review.term_id)
Index("ix_tasks_status_lease", DurableTask.status, DurableTask.lease_until)
Index("ix_outbox_pending", OutboxEvent.processed_at, OutboxEvent.claimed_until)
