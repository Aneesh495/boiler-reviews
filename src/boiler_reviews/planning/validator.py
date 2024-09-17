from __future__ import annotations

from dataclasses import dataclass

from boiler_reviews.catalog.ast import (
    AllOf,
    AnyOf,
    CoRequisite,
    CourseRef,
    CreditsAtLeast,
    Expr,
    GradeAtLeast,
    Predicate,
)
from boiler_reviews.planning.model import PlanRequest


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    violations: tuple[str, ...]


def _evaluate(expr: Expr | None, *, target_term: int, assignment: dict[str, int], request: PlanRequest, coreq: bool = False) -> tuple[bool, tuple[str, ...]]:
    if expr is None:
        return True, ()
    course_map = request.course_map()
    if isinstance(expr, CourseRef):
        if expr.code in request.completed:
            return True, ()
        if expr.code not in assignment or assignment[expr.code] == 0:
            return False, (f"{expr.code} is not completed or scheduled",)
        relation_ok = assignment[expr.code] == target_term if coreq else assignment[expr.code] < target_term
        return relation_ok, (f"{expr.code} must be {'in' if coreq else 'before'} term {target_term}",) if not relation_ok else ()
    if isinstance(expr, GradeAtLeast):
        if expr.course.code not in request.completed:
            return False, (f"{expr.course.code} must be completed with grade {expr.grade}",)
        order = {"A+": 4.3, "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "F": 0.0}
        if order.get(request.grades.get(expr.course.code, "F"), 0) < order.get(expr.grade, 0):
            return False, (f"{expr.course.code} grade is below {expr.grade}",)
        return True, ()
    if isinstance(expr, CreditsAtLeast):
        earned = request.completed_credits + sum(course_map[code].credit_units for code, term in assignment.items() if term and term < target_term and code in course_map) // 1000
        return earned >= expr.credits, (f"at least {expr.credits} credits must be earned before term {target_term}",) if earned < expr.credits else ()
    if isinstance(expr, Predicate):
        values = request.permissions if expr.kind == "permission" else request.placements
        return expr.value in values, (f"{expr.kind} {expr.value} is unresolved",) if expr.value not in values else ()
    if isinstance(expr, AllOf):
        results = [_evaluate(item, target_term=target_term, assignment=assignment, request=request, coreq=coreq) for item in expr.items]
        return all(value for value, _ in results), tuple(reason for _, reasons in results for reason in reasons)
    if isinstance(expr, AnyOf):
        results = [_evaluate(item, target_term=target_term, assignment=assignment, request=request, coreq=coreq) for item in expr.items]
        return any(value for value, _ in results), tuple(reason for _, reasons in results for reason in reasons)
    if isinstance(expr, CoRequisite):
        results = [_evaluate(item, target_term=target_term, assignment=assignment, request=request, coreq=True) for item in expr.items]
        return all(value for value, _ in results), tuple(reason for _, reasons in results for reason in reasons)
    raise TypeError(f"unsupported AST node {type(expr)!r}")


def validate_plan(request: PlanRequest, assignment: dict[str, int]) -> ValidationResult:
    violations: list[str] = list(request.validate_input())
    course_map = request.course_map()
    term_map = request.term_map()
    if set(assignment) - set(course_map):
        violations.append("plan contains a course outside the request")
    for code, term in assignment.items():
        course = course_map.get(code)
        if course is None:
            continue
        if term not in term_map and term != 0:
            violations.append(f"{code} uses unknown term {term}")
        if code in request.pinned and request.pinned[code] != term:
            violations.append(f"{code} violates pinned term {request.pinned[code]}")
        if term == 0:
            continue
        if course.available_terms and term not in course.available_terms:
            violations.append(f"{code} is unavailable in term {term}")
        if code in request.excluded:
            violations.append(f"{code} is excluded")
        if code in request.pinned and request.pinned[code] != term:
            violations.append(f"{code} violates pinned term {request.pinned[code]}")
        if term and course.prerequisites is not None:
            valid, reasons = _evaluate(course.prerequisites, target_term=term, assignment=assignment, request=request)
            if not valid:
                violations.extend(f"{code}: {reason}" for reason in reasons)
        for coreq in course.co_requisites:
            if coreq in assignment and assignment[coreq] != term:
                violations.append(f"{code} and {coreq} must be co-requisite in term {term}")
    for term in term_map:
        credits = sum(course_map[code].credit_units for code, assigned in assignment.items() if assigned == term and code in course_map) // 1000
        if credits < term_map[term].min_credits:
            violations.append(f"term {term} has {credits} credits below minimum {term_map[term].min_credits}")
        if credits > term_map[term].max_credits:
            violations.append(f"term {term} has {credits} credits above maximum {term_map[term].max_credits}")
    allocations: dict[str, str] = {}
    for group in request.requirements:
        selected = [code for code, term in assignment.items() if term and code in course_map and code in group.course_codes]
        credits = sum(course_map[code].credit_units for code in selected) // 1000
        if len(selected) < group.min_courses:
            violations.append(f"requirement {group.label} needs {group.min_courses} course(s), got {len(selected)}")
        if credits < group.min_credits:
            violations.append(f"requirement {group.label} needs {group.min_credits} credits, got {credits}")
        if not group.allow_double_counting:
            for code in selected:
                if code in allocations:
                    violations.append(f"{code} is allocated to multiple requirement groups")
                allocations[code] = group.id
    return ValidationResult(not violations, tuple(dict.fromkeys(violations)))
