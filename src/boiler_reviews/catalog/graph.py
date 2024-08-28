from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from boiler_reviews.catalog.ast import AllOf, AnyOf, CoRequisite, CourseRef, Expr, GradeAtLeast, Predicate, CreditsAtLeast


@dataclass(frozen=True, slots=True)
class GraphEdge:
    prerequisite: str
    dependent: str
    relation: str
    source_text: str


@dataclass(frozen=True, slots=True)
class CycleReport:
    nodes: tuple[str, ...]
    relations: tuple[str, ...]
    legitimate_corequisite_group: bool


@dataclass(frozen=True, slots=True)
class Eligibility:
    state: str
    reasons: tuple[str, ...]


class PrerequisiteGraph:
    def __init__(self, expressions: dict[str, Expr], provenance: dict[str, str] | None = None) -> None:
        self.expressions = expressions
        self.provenance = provenance or {}
        self.edges = self._edges()

    def _edges(self) -> tuple[GraphEdge, ...]:
        edges: list[GraphEdge] = []
        for dependent, expression in self.expressions.items():
            self._walk_edges(expression, dependent, "strict", edges)
        return tuple(edges)

    def _walk_edges(self, expression: Expr, dependent: str, relation: str, edges: list[GraphEdge]) -> None:
        if isinstance(expression, CourseRef):
            edges.append(GraphEdge(expression.code, dependent, relation, self.provenance.get(dependent, "")))
        elif isinstance(expression, GradeAtLeast):
            edges.append(GraphEdge(expression.course.code, dependent, relation, self.provenance.get(dependent, "")))
        elif isinstance(expression, CoRequisite):
            for item in expression.items:
                self._walk_edges(item, dependent, "corequisite", edges)
        elif isinstance(expression, (AllOf, AnyOf)):
            for item in expression.items:
                self._walk_edges(item, dependent, relation, edges)
        elif isinstance(expression, (Predicate, CreditsAtLeast)):
            return

    def unknown_references(self, known_courses: Iterable[str]) -> set[str]:
        known = set(known_courses)
        return {edge.prerequisite for edge in self.edges if edge.prerequisite not in known}

    def strict_cycles(self) -> tuple[CycleReport, ...]:
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.prerequisite, []).append((edge.dependent, edge.relation))
            adjacency.setdefault(edge.dependent, [])
        index = 0
        indices: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        reports: list[CycleReport] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = index
            low[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for neighbor, _ in adjacency[node]:
                if neighbor not in indices:
                    visit(neighbor)
                    low[node] = min(low[node], low[neighbor])
                elif neighbor in on_stack:
                    low[node] = min(low[node], indices[neighbor])
            if low[node] == indices[node]:
                component: list[str] = []
                while True:
                    value = stack.pop()
                    on_stack.remove(value)
                    component.append(value)
                    if value == node:
                        break
                component_set = set(component)
                component_edges = [edge for edge in self.edges if edge.prerequisite in component_set and edge.dependent in component_set]
                if len(component) > 1 or any(edge.prerequisite == edge.dependent for edge in component_edges):
                    relations = tuple(sorted({edge.relation for edge in component_edges}))
                    reports.append(CycleReport(tuple(sorted(component)), relations, relations == ("corequisite",)))

        for node in sorted(adjacency):
            if node not in indices:
                visit(node)
        return tuple(reports)

    def dependency_path(self, start: str, target: str) -> tuple[str, ...] | None:
        adjacency: dict[str, list[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.dependent, []).append(edge.prerequisite)
        frontier: list[tuple[str, tuple[str, ...]]] = [(start, (start,))]
        visited = {start}
        while frontier:
            current, path = frontier.pop(0)
            if current == target:
                return path
            for prerequisite in sorted(adjacency.get(current, [])):
                if prerequisite not in visited:
                    visited.add(prerequisite)
                    frontier.append((prerequisite, path + (prerequisite,)))
        return None


def evaluate(expression: Expr, *, completed: set[str], in_term: set[str], earned_credits: int, permissions: set[str] | None = None, placements: set[str] | None = None, grades: dict[str, str] | None = None) -> Eligibility:
    permissions = permissions or set()
    placements = placements or set()
    grades = grades or {}
    if isinstance(expression, CourseRef):
        if expression.code in completed or expression.code in in_term:
            return Eligibility("satisfied", (f"{expression.code} is completed or co-requisite",))
        return Eligibility("unsatisfied", (f"Complete {expression.code} first",))
    if isinstance(expression, GradeAtLeast):
        order = {"A+": 4.3, "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "F": 0.0}
        actual = order.get(grades.get(expression.course.code, "F"), 0.0)
        required = order.get(expression.grade, 0.0)
        if expression.course.code in completed and actual >= required:
            return Eligibility("satisfied", (f"{expression.course.code} grade meets {expression.grade}",))
        return Eligibility("unsatisfied", (f"{expression.course.code} requires grade {expression.grade}",))
    if isinstance(expression, CreditsAtLeast):
        return Eligibility("satisfied" if earned_credits >= expression.credits else "unsatisfied", (f"Requires {expression.credits} earned credits",))
    if isinstance(expression, Predicate):
        values = permissions if expression.kind == "permission" else placements
        if expression.value in values:
            return Eligibility("satisfied", (f"{expression.kind} {expression.value} supplied",))
        return Eligibility("unknown", (f"{expression.kind.title()} {expression.value} has not been verified",))
    if isinstance(expression, AllOf):
        results = [evaluate(item, completed=completed, in_term=in_term, earned_credits=earned_credits, permissions=permissions, placements=placements, grades=grades) for item in expression.items]
        if any(result.state == "unsatisfied" for result in results):
            return Eligibility("unsatisfied", tuple(reason for result in results for reason in result.reasons))
        if any(result.state == "unknown" for result in results):
            return Eligibility("unknown", tuple(reason for result in results for reason in result.reasons))
        return Eligibility("satisfied", tuple(reason for result in results for reason in result.reasons))
    if isinstance(expression, AnyOf):
        results = [evaluate(item, completed=completed, in_term=in_term, earned_credits=earned_credits, permissions=permissions, placements=placements, grades=grades) for item in expression.items]
        if any(result.state == "satisfied" for result in results):
            return Eligibility("satisfied", tuple(reason for result in results for reason in result.reasons))
        if all(result.state == "unsatisfied" for result in results):
            return Eligibility("unsatisfied", tuple(reason for result in results for reason in result.reasons))
        return Eligibility("unknown", tuple(reason for result in results for reason in result.reasons))
    if isinstance(expression, CoRequisite):
        return evaluate(AllOf(expression.items), completed=completed, in_term=in_term, earned_credits=earned_credits, permissions=permissions, placements=placements, grades=grades)
    raise TypeError(f"unsupported expression {type(expression)!r}")
