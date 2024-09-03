from __future__ import annotations

import random

from boiler_reviews.planning.model import CourseSpec, PlanRequest, TermSpec
from boiler_reviews.planning.oracle import enumerate_optimum
from boiler_reviews.planning.solver import solve
from boiler_reviews.planning.validator import validate_plan


def test_bounded_generated_curricula_agree_with_oracle():
    random.seed(20261001)
    for index in range(40):
        courses = tuple(CourseSpec(f"C{index}_{course}", 1000, frozenset({1, 2})) for course in ("A", "B", "C"))
        request = PlanRequest(courses=courses, terms=(TermSpec("one", 1, 0, 2), TermSpec("two", 2, 0, 2)), time_limit_seconds=3)
        solver_result = solve(request)[0]
        oracle = enumerate_optimum(request)
        assert solver_result.status == "optimal"
        assert oracle.feasible
        assert validate_plan(request, solver_result.assignment).valid
        assert solver_result.objective_value == oracle.objective_value
