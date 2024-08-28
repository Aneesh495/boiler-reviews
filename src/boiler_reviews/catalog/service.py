from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.catalog.ast import Expr
from boiler_reviews.catalog.graph import PrerequisiteGraph
from boiler_reviews.catalog.parser import ast_to_json, parse_prerequisites
from boiler_reviews.catalog.schema import CatalogDocument
from boiler_reviews.common.errors import ConflictError, NotFoundError, ValidationError
from boiler_reviews.db.models import AuditEvent, CatalogSnapshot, Course, CourseVersion, Institution, Term


@dataclass(frozen=True, slots=True)
class CatalogValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    parsed_courses: int
    unsupported_courses: int

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class CatalogDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    renamed: tuple[dict[str, str], ...]
    credit_changes: tuple[dict[str, Any], ...]
    prerequisite_changes: tuple[dict[str, Any], ...]
    availability_changes: tuple[dict[str, Any], ...]


def canonical_payload(document: CatalogDocument) -> bytes:
    return json.dumps(document.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()


def validate_catalog(document: CatalogDocument) -> CatalogValidation:
    errors: list[str] = []
    warnings: list[str] = []
    codes = [course.code for course in document.courses]
    if len(codes) != len(set(codes)):
        errors.append("duplicate course codes")
    if len({(term.name, term.year) for term in document.terms}) != len(document.terms):
        errors.append("duplicate terms")
    known = set(codes)
    expressions: dict[str, Expr] = {}
    parsed = unsupported = 0
    for course in document.courses:
        result = parse_prerequisites(course.prerequisites)
        if result.status == "parsed" and result.ast is not None:
            parsed += 1
            expressions[course.code] = result.ast
        else:
            unsupported += 1
            warnings.append(f"{course.code}: prerequisite text remains unresolved")
    graph = PrerequisiteGraph(expressions, {course.code: course.prerequisites or "" for course in document.courses})
    unknown = graph.unknown_references(known)
    errors.extend(f"unknown prerequisite course {code}" for code in sorted(unknown))
    for cycle in graph.strict_cycles():
        if not cycle.legitimate_corequisite_group:
            errors.append(f"strict prerequisite cycle: {' -> '.join(cycle.nodes)}")
    return CatalogValidation(tuple(errors), tuple(warnings), parsed, unsupported)


def parse_document(payload: dict[str, Any]) -> CatalogDocument:
    try:
        document = CatalogDocument.model_validate(payload)
    except PydanticValidationError as error:
        raise ValidationError("Catalog document failed schema validation.", fields={str(item["loc"]): item["msg"] for item in error.errors()}) from error
    result = validate_catalog(document)
    if not result.valid:
        raise ValidationError("Catalog document failed semantic validation.", fields={str(index): value for index, value in enumerate(result.errors)})
    return document


def stage_catalog(session: Session, *, payload: dict[str, Any]) -> tuple[CatalogSnapshot, CatalogValidation]:
    document = parse_document(payload)
    institution = session.scalar(select(Institution).where(Institution.code == document.institution_code))
    if institution is None:
        institution = Institution(name=document.institution_name, code=document.institution_code, timezone=document.timezone)
        session.add(institution)
        session.flush()
    existing = session.scalar(select(CatalogSnapshot).where(CatalogSnapshot.institution_id == institution.id, CatalogSnapshot.version == document.version))
    if existing is not None:
        return existing, validate_catalog(document)
    snapshot = CatalogSnapshot(
        institution_id=institution.id,
        version=document.version,
        status="staged",
        source_uri=document.source_uri,
        content_hash=hashlib.sha256(canonical_payload(document)).hexdigest(),
        provenance_json=document.provenance,
    )
    session.add(snapshot)
    session.flush()
    course_by_code: dict[str, Course] = {}
    for item in document.courses:
        stable_code = item.stable_code or item.code
        course = session.scalar(select(Course).where(Course.institution_id == institution.id, Course.stable_code == stable_code))
        if course is None:
            course = Course(institution_id=institution.id, stable_code=stable_code, canonical_title=item.title)
            session.add(course)
            session.flush()
        course_by_code[item.code] = course
        parsed = parse_prerequisites(item.prerequisites)
        session.add(
            CourseVersion(
                course_id=course.id,
                snapshot_id=snapshot.id,
                code=item.code,
                title=item.title,
                credit_units=item.credits * 1000,
                description=item.description,
                prerequisite_text=item.prerequisites,
                prerequisite_ast=ast_to_json(parsed),
                prerequisite_status=parsed.status,
                availability_json=item.availability,
            )
        )
    for term_data in document.terms:
        existing_term = session.scalar(select(Term).where(Term.institution_id == institution.id, Term.name == term_data.name, Term.year == term_data.year))
        if existing_term is None:
            session.add(Term(institution_id=institution.id, name=term_data.name, year=term_data.year, starts_on=term_data.starts_on, ends_on=term_data.ends_on))
    session.add(AuditEvent(actor_id=None, event_type="catalog.staged", entity_type="catalog_snapshot", entity_id=snapshot.id, payload_json={"version": document.version, "warnings": list(validate_catalog(document).warnings)}))
    return snapshot, validate_catalog(document)


def activate_catalog(session: Session, *, snapshot_id: str) -> CatalogSnapshot:
    snapshot = session.get(CatalogSnapshot, snapshot_id)
    if snapshot is None:
        raise NotFoundError("Catalog snapshot not found.")
    if snapshot.status not in {"staged", "active"}:
        raise ConflictError(f"Snapshot is {snapshot.status} and cannot be activated.")
    previous = session.scalars(select(CatalogSnapshot).where(CatalogSnapshot.institution_id == snapshot.institution_id, CatalogSnapshot.status == "active", CatalogSnapshot.id != snapshot.id).with_for_update()).all()
    for value in previous:
        value.status = "archived"
    snapshot.status = "active"
    snapshot.activated_at = datetime.now(timezone.utc)
    session.add(AuditEvent(actor_id=None, event_type="catalog.activated", entity_type="catalog_snapshot", entity_id=snapshot.id, payload_json={"previous": [value.id for value in previous]}))
    return snapshot


def compare_documents(old: CatalogDocument, new: CatalogDocument) -> CatalogDiff:
    before = {course.code: course for course in old.courses}
    after = {course.code: course for course in new.courses}
    added = tuple(sorted(set(after) - set(before)))
    removed = tuple(sorted(set(before) - set(after)))
    renamed: list[dict[str, str]] = []
    credit_changes: list[dict[str, Any]] = []
    prerequisite_changes: list[dict[str, Any]] = []
    availability_changes: list[dict[str, Any]] = []
    for code in sorted(set(before) & set(after)):
        left, right = before[code], after[code]
        if left.title != right.title:
            renamed.append({"code": code, "from": left.title, "to": right.title})
        if left.credits != right.credits:
            credit_changes.append({"code": code, "from": left.credits, "to": right.credits})
        if left.prerequisites != right.prerequisites:
            prerequisite_changes.append({"code": code, "from": left.prerequisites, "to": right.prerequisites})
        if left.availability != right.availability:
            availability_changes.append({"code": code, "from": left.availability, "to": right.availability})
    return CatalogDiff(added, removed, tuple(renamed), tuple(credit_changes), tuple(prerequisite_changes), tuple(availability_changes))
