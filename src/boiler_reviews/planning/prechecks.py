from __future__ import annotations

from dataclasses import dataclass

from boiler_reviews.planning.model import PlanRequest


@dataclass(frozen=True, slots=True)
class Precheck:
    valid: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


def precheck(request: PlanRequest) -> Precheck:
    failures = list(request.validate_input())
    warnings: list[str] = []
    terms = {term.index: term for term in request.terms}
    courses = request.course_map()
    for code, term in request.pinned.items():
        if code not in courses:
            continue
        course = courses[code]
        if course.available_terms and term not in course.available_terms:
            failures.append(f"pin:{code} selects unavailable term {term}")
        if term not in terms:
            failures.append(f"pin:{code} references unknown term {term}")
    total_required = sum(group.min_credits for group in request.requirements)
    total_capacity = sum(term.max_credits for term in request.terms)
    if total_required > total_capacity:
        failures.append(f"requirement credits {total_required} exceed total term capacity {total_capacity}")
    for group in request.requirements:
        eligible = group.course_codes & set(courses)
        eligible_credits = sum(courses[code].credit_units for code in eligible) // 1000
        if eligible_credits < group.min_credits:
            failures.append(f"requirement:{group.id} has only {eligible_credits} eligible credits")
        if len(eligible) < group.min_courses:
            failures.append(f"requirement:{group.id} has only {len(eligible)} eligible courses")
    if len(request.courses) > 100:
        warnings.append("large planning request: solver status and bound must be preserved")
    if any(course.prerequisites is not None for course in request.courses):
        warnings.append("prerequisite constraints require independent validation")
    return Precheck(not failures, tuple(dict.fromkeys(failures)), tuple(warnings))
