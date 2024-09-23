from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from boiler_reviews.planning.model import PlanRequest, PlanResult


@dataclass(frozen=True, slots=True)
class ObjectiveVector:
    completion_terms: int
    peak_workload: int
    preference_points: int
    selected_credits: int

    def dominates(self, other: ObjectiveVector) -> bool:
        better_or_equal = self.completion_terms <= other.completion_terms and self.peak_workload <= other.peak_workload and self.preference_points >= other.preference_points and self.selected_credits >= other.selected_credits
        strictly_better = self.completion_terms < other.completion_terms or self.peak_workload < other.peak_workload or self.preference_points > other.preference_points or self.selected_credits > other.selected_credits
        return better_or_equal and strictly_better


def objective_vector(request: PlanRequest, assignment: dict[str, int]) -> ObjectiveVector:
    term_loads = [sum(course.workload_hours for course in request.courses if assignment.get(course.code) == term.index) for term in request.terms]
    completion_terms = sum(assignment.get(course.code, 0) for course in request.courses if assignment.get(course.code, 0))
    preference = sum(course.preference_score for course in request.courses if assignment.get(course.code, 0))
    credits = sum(course.credit_units for course in request.courses if assignment.get(course.code, 0))
    return ObjectiveVector(completion_terms, max(term_loads, default=0), preference, credits)


def pareto_frontier(request: PlanRequest, results: Iterable[PlanResult]) -> tuple[PlanResult, ...]:
    feasible = [result for result in results if result.feasible and result.assignment]
    vectors = [objective_vector(request, result.assignment) for result in feasible]
    frontier: list[PlanResult] = []
    for index, candidate in enumerate(feasible):
        if not any(other.dominates(vectors[index]) for other in vectors if other is not vectors[index]):
            frontier.append(candidate)
    return tuple(frontier)


def tradeoff_summary(request: PlanRequest, results: Iterable[PlanResult]) -> list[dict[str, object]]:
    return [{"status": result.status, "assignment": result.assignment, "objective": objective_vector(request, result.assignment).__dict__ if hasattr(objective_vector(request, result.assignment), "__dict__") else {"completion_terms": objective_vector(request, result.assignment).completion_terms, "peak_workload": objective_vector(request, result.assignment).peak_workload, "preference_points": objective_vector(request, result.assignment).preference_points, "selected_credits": objective_vector(request, result.assignment).selected_credits}} for result in pareto_frontier(request, results)]
