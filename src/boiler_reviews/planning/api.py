from __future__ import annotations

from typing import Any

from boiler_reviews.catalog.ast import expr_from_dict
from boiler_reviews.planning.model import CourseSpec, PlanRequest, RequirementGroup, TermSpec
from boiler_reviews.planning.prechecks import precheck


def request_from_json(payload: dict[str, Any]) -> PlanRequest:
    term_values = payload.get("terms", [])
    terms = tuple(TermSpec(str(item["id"]), int(item["index"]), int(item.get("min_credits", 0)), int(item["max_credits"])) for item in term_values)
    courses = []
    for item in payload.get("courses", []):
        prerequisites = expr_from_dict(item["prerequisites"]) if item.get("prerequisites") else None
        courses.append(CourseSpec(
            code=str(item["code"]),
            credit_units=int(item.get("credit_units", int(item.get("credits", 0) * 1000))),
            available_terms=frozenset(int(value) for value in item.get("available_terms", [])),
            prerequisites=prerequisites,
            workload_hours=int(item.get("workload_hours", 0)),
            preference_score=int(item.get("preference_score", 0)),
            co_requisites=frozenset(str(value) for value in item.get("co_requisites", [])),
            requirement_groups=frozenset(str(value) for value in item.get("requirement_groups", [])),
            section_ids=tuple(str(value) for value in item.get("section_ids", [])),
        ))
    requirements = tuple(RequirementGroup(
        id=str(item["id"]),
        label=str(item.get("label", item["id"])),
        course_codes=frozenset(str(value) for value in item.get("course_codes", [])),
        min_courses=int(item.get("min_courses", 1)),
        min_credits=int(item.get("min_credits", 0)),
        allow_double_counting=bool(item.get("allow_double_counting", False)),
        unknown=bool(item.get("unknown", False)),
    ) for item in payload.get("requirements", []))
    return PlanRequest(
        courses=tuple(courses),
        terms=terms,
        requirements=requirements,
        completed=frozenset(str(value) for value in payload.get("completed", [])),
        completed_credits=int(payload.get("completed_credits", 0)),
        grades={str(key): str(value) for key, value in payload.get("grades", {}).items()},
        permissions=frozenset(str(value) for value in payload.get("permissions", [])),
        placements=frozenset(str(value) for value in payload.get("placements", [])),
        pinned={str(key): int(value) for key, value in payload.get("pinned", {}).items()},
        excluded=frozenset(str(value) for value in payload.get("excluded", [])),
        objective=str(payload.get("objective", "earliest_completion")),
        time_limit_seconds=float(payload.get("time_limit_seconds", 15)),
        random_seed=int(payload.get("random_seed", 20261001)),
    )


def plan_result_payload(result: Any) -> dict[str, Any]:
    validator = result.validator
    return {
        "status": result.status,
        "assignment": result.assignment,
        "objective_value": result.objective_value,
        "best_bound": result.best_bound,
        "diagnostics": list(result.diagnostics),
        "assumption_core": list(result.assumption_core),
        "validator": None if validator is None else {"valid": validator.valid, "violations": list(validator.violations)},
    }


def precheck_payload(request: PlanRequest) -> dict[str, Any]:
    result = precheck(request)
    return {"valid": result.valid, "failures": list(result.failures), "warnings": list(result.warnings)}
