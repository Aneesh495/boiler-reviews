from __future__ import annotations

from boiler_reviews.catalog.parser import parse_prerequisites
from boiler_reviews.planning.model import CourseSpec, PlanRequest, RequirementGroup, TermSpec
from boiler_reviews.planning.oracle import enumerate_optimum
from boiler_reviews.planning.solver import solve
from boiler_reviews.planning.validator import validate_plan


def request() -> PlanRequest:
    return PlanRequest(
        courses=(
            CourseSpec("AA101", 3000, frozenset({1}), workload_hours=3, requirement_groups=frozenset({"core"})),
            CourseSpec("BB101", 3000, frozenset({2}), prerequisites=parse_prerequisites("AA101").ast, workload_hours=4, requirement_groups=frozenset({"core"})),
        ),
        terms=(TermSpec("t1", 1, 0, 3), TermSpec("t2", 2, 0, 3)),
        requirements=(RequirementGroup("core", "Core", frozenset({"AA101", "BB101"}), min_courses=2, min_credits=6),),
        objective="earliest_completion",
        time_limit_seconds=5,
    )


def test_solver_result_passes_independent_validator_and_matches_oracle():
    model = request()
    result = solve(model)[0]
    assert result.status == "optimal"
    assert validate_plan(model, result.assignment).valid
    oracle = enumerate_optimum(model)
    assert oracle.feasible
    assert oracle.objective_value == result.objective_value


def test_infeasible_pin_is_reported_without_timeout_claim():
    model = request()
    pinned = PlanRequest(**{**model.__dict__, "pinned": {"B": 1}}) if hasattr(model, "__dict__") else PlanRequest(courses=model.courses, terms=model.terms, requirements=model.requirements, pinned={"BB101": 1}, objective=model.objective, time_limit_seconds=5)
    result = solve(pinned)[0]
    assert result.status == "infeasible"
    assert result.status != "unknown"


def test_validator_rejects_same_term_strict_prerequisite():
    model = request()
    invalid = validate_plan(model, {"AA101": 1, "BB101": 1})
    assert not invalid.valid
    assert any("before" in violation for violation in invalid.violations)
