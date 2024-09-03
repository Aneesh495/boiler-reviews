from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from boiler_reviews.planning.model import PlanRequest
from boiler_reviews.planning.validator import ValidationResult, validate_plan


@dataclass(frozen=True, slots=True)
class OracleResult:
    feasible: bool
    assignment: dict[str, int] | None
    objective_value: int | None
    checked_assignments: int
    truncated: bool


def objective_value(request: PlanRequest, assignment: dict[str, int]) -> int:
    selected = [term for term in assignment.values() if term]
    if not selected:
        return 0
    if request.objective == "balanced_workload":
        return -max(sum(course.workload_hours for course in request.courses if assignment.get(course.code) == term) for term in range(1, len(request.terms) + 1))
    if request.objective == "preference_satisfaction":
        return sum(course.preference_score for course in request.courses if assignment.get(course.code, 0))
    return sum((len(request.terms) + 1 - term) for term in selected)


def enumerate_optimum(request: PlanRequest, *, max_assignments: int = 100_000) -> OracleResult:
    codes = [course.code for course in request.courses]
    choices = [tuple([0, *sorted(course.available_terms or {term.index for term in request.terms})]) for course in request.courses]
    best: tuple[int, dict[str, int]] | None = None
    checked = 0
    for values in product(*choices):
        checked += 1
        assignment = dict(zip(codes, values))
        result: ValidationResult = validate_plan(request, assignment)
        if result.valid:
            score = objective_value(request, assignment)
            if best is None or score > best[0]:
                best = (score, assignment)
        if checked >= max_assignments:
            return OracleResult(best is not None, None if best is None else best[1], None if best is None else best[0], checked, True)
    return OracleResult(best is not None, None if best is None else best[1], None if best is None else best[0], checked, False)
