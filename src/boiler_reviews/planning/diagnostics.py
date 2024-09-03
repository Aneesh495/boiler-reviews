from __future__ import annotations

from dataclasses import dataclass

from boiler_reviews.planning.model import PlanRequest
from boiler_reviews.planning.validator import validate_plan


@dataclass(frozen=True, slots=True)
class Relaxation:
    constraint: str
    reason: str
    checked: bool


@dataclass(frozen=True, slots=True)
class Diagnostic:
    proven_infeasible: bool
    assumption_core: tuple[str, ...]
    relaxations: tuple[Relaxation, ...]
    limitation: str | None = None


def explain_infeasibility(request: PlanRequest, *, base_assignment: dict[str, int] | None = None) -> Diagnostic:
    """Return checked one-at-a-time relaxations, not a claimed minimal core."""
    assignment = base_assignment or {}
    violations = validate_plan(request, assignment).violations
    core = tuple(sorted({f"pin:{code}" for code in request.pinned if any(code in violation for violation in violations)} | {f"term_budget:{term.index}" for term in request.terms if any(f"term {term.index}" in violation for violation in violations)}))
    relaxations: list[Relaxation] = []
    for code, term in request.pinned.items():
        changed = dict(request.pinned)
        changed.pop(code)
        relaxed = PlanRequest(**{**request.__dict__, "pinned": changed}) if hasattr(request, "__dict__") else PlanRequest(courses=request.courses, terms=request.terms, requirements=request.requirements, completed=request.completed, completed_credits=request.completed_credits, grades=request.grades, permissions=request.permissions, placements=request.placements, pinned=changed, excluded=request.excluded, objective=request.objective, time_limit_seconds=request.time_limit_seconds, random_seed=request.random_seed)
        valid = not validate_plan(relaxed, assignment).violations
        relaxations.append(Relaxation(f"pin:{code}", f"Remove the pin from {code} and revalidate the supplied assignment", valid))
    return Diagnostic(bool(violations), core, tuple(relaxations), "The suggestions are checked single-constraint relaxations, not a minimal unsatisfiable core.")
