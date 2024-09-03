from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from boiler_reviews.catalog.ast import Expr


@dataclass(frozen=True, slots=True)
class TermSpec:
    id: str
    index: int
    min_credits: int
    max_credits: int
    starts_on: str | None = None
    ends_on: str | None = None

    def __post_init__(self) -> None:
        if self.index < 1 or self.min_credits < 0 or self.max_credits < self.min_credits:
            raise ValueError("term bounds are invalid")


@dataclass(frozen=True, slots=True)
class CourseSpec:
    code: str
    credit_units: int
    available_terms: frozenset[int]
    prerequisites: Expr | None = None
    workload_hours: int = 0
    preference_score: int = 0
    co_requisites: frozenset[str] = frozenset()
    requirement_groups: frozenset[str] = frozenset()
    section_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RequirementGroup:
    id: str
    label: str
    course_codes: frozenset[str]
    min_courses: int = 1
    min_credits: int = 0
    allow_double_counting: bool = False
    unknown: bool = False


@dataclass(frozen=True, slots=True)
class PlanRequest:
    courses: tuple[CourseSpec, ...]
    terms: tuple[TermSpec, ...]
    requirements: tuple[RequirementGroup, ...] = ()
    completed: frozenset[str] = frozenset()
    completed_credits: int = 0
    grades: dict[str, str] = field(default_factory=dict)
    permissions: frozenset[str] = frozenset()
    placements: frozenset[str] = frozenset()
    pinned: dict[str, int] = field(default_factory=dict)
    excluded: frozenset[str] = frozenset()
    objective: str = "earliest_completion"
    time_limit_seconds: float = 15.0
    random_seed: int = 20261001

    def course_map(self) -> dict[str, CourseSpec]:
        return {course.code: course for course in self.courses}

    def term_map(self) -> dict[int, TermSpec]:
        return {term.index: term for term in self.terms}

    def validate_input(self) -> tuple[str, ...]:
        errors: list[str] = []
        course_map = self.course_map()
        if len(course_map) != len(self.courses):
            errors.append("duplicate course identity")
        term_indices = set(self.term_map())
        if len(term_indices) != len(self.terms):
            errors.append("duplicate term index")
        for code, index in self.pinned.items():
            if code not in course_map:
                errors.append(f"pinned course {code} is not in the catalog")
            elif index not in term_indices:
                errors.append(f"pinned course {code} references unknown term {index}")
        for course in self.courses:
            if course.credit_units <= 0:
                errors.append(f"{course.code} has non-positive credits")
            unknown_groups = course.requirement_groups - {group.id for group in self.requirements}
            errors.extend(f"{course.code} references unknown requirement group {group}" for group in unknown_groups)
            unknown_coreqs = course.co_requisites - set(course_map) - set(self.completed)
            errors.extend(f"{course.code} references unknown co-requisite {coreq}" for coreq in unknown_coreqs)
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class PlanResult:
    status: str
    assignment: dict[str, int]
    objective_value: int | None
    best_bound: float | None
    diagnostics: tuple[str, ...] = ()
    assumption_core: tuple[str, ...] = ()
    validator: Any | None = None

    @property
    def proven_optimal(self) -> bool:
        return self.status == "optimal"

    @property
    def feasible(self) -> bool:
        return self.status in {"optimal", "feasible"}
