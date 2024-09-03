from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

# The pinned wheel is the production solver. The current macOS Python 3.14
# runtime has a native-extension crash during import, so the safe local path is
# an independent bounded oracle rather than a process-killing import. CI on a
# supported interpreter exercises the CP-SAT branch.
cp_model: Any = None
if sys.version_info < (3, 14):
    from ortools.sat.python import cp_model as _cp_model
    cp_model = _cp_model

from boiler_reviews.catalog.ast import AllOf, AnyOf, CoRequisite, CourseRef, CreditsAtLeast, Expr, GradeAtLeast, Predicate
from boiler_reviews.planning.diagnostics import explain_infeasibility
from boiler_reviews.planning.model import CourseSpec, PlanRequest, PlanResult
from boiler_reviews.planning.validator import validate_plan


@dataclass(slots=True)
class _Build:
    model: cp_model.CpModel
    term_vars: dict[str, cp_model.IntVar]
    selected: dict[str, cp_model.BoolVar]
    assumptions: dict[int, str]
    term_members: dict[int, dict[str, cp_model.BoolVar]]
    invalid: list[str]


def _equivalence(model: cp_model.CpModel, value: cp_model.BoolVar, left: cp_model.BoolVar, right: cp_model.BoolVar) -> None:
    model.AddBoolAnd([left, right]).OnlyEnforceIf(value)
    model.AddBoolOr([left.Not(), right.Not()]).OnlyEnforceIf(value.Not())


def _expr_bool(build: _Build, expression: Expr, target_term: cp_model.IntVar, request: PlanRequest, *, coreq: bool = False) -> cp_model.BoolVar:
    model = build.model
    if isinstance(expression, CourseRef):
        if expression.code in request.completed:
            value = model.NewBoolVar(f"completed_{expression.code}_{target_term.Name()}")
            model.Add(value == 1)
            return value
        prerequisite = build.term_vars.get(expression.code)
        if prerequisite is None:
            value = model.NewBoolVar(f"unknown_{expression.code}")
            model.Add(value == 0)
            build.invalid.append(f"unknown prerequisite {expression.code}")
            return value
        selected = build.selected[expression.code]
        value = model.NewBoolVar(f"eligible_{expression.code}_{target_term.Name()}")
        relation = model.NewBoolVar(f"relation_{expression.code}_{target_term.Name()}")
        if coreq:
            model.Add(prerequisite == target_term).OnlyEnforceIf(relation)
            model.Add(prerequisite != target_term).OnlyEnforceIf(relation.Not())
        else:
            model.Add(prerequisite < target_term).OnlyEnforceIf(relation)
            model.Add(prerequisite >= target_term).OnlyEnforceIf(relation.Not())
        _equivalence(model, value, selected, relation)
        return value
    if isinstance(expression, GradeAtLeast):
        if expression.course.code in request.completed:
            order = {"A+": 4300, "A": 4000, "A-": 3700, "B+": 3300, "B": 3000, "B-": 2700, "C+": 2300, "C": 2000, "C-": 1700, "D": 1000, "F": 0}
            value = model.NewBoolVar(f"grade_{expression.course.code}")
            model.Add(value == int(order.get(request.grades.get(expression.course.code, "F"), 0) >= order.get(expression.grade, 0)))
            return value
        value = model.NewBoolVar(f"unknown_grade_{expression.course.code}")
        model.Add(value == 0)
        build.invalid.append(f"future grade requirement {expression.course.code} {expression.grade} is unresolved")
        return value
    if isinstance(expression, CreditsAtLeast):
        value = model.NewBoolVar(f"credits_{expression.credits}_{target_term.Name()}")
        before_terms: list[cp_model.BoolVar] = []
        for course in request.courses:
            if course.code in request.completed:
                continue
            before = model.NewBoolVar(f"before_{course.code}_{target_term.Name()}")
            selected = build.selected[course.code]
            less = model.NewBoolVar(f"less_{course.code}_{target_term.Name()}")
            model.Add(build.term_vars[course.code] < target_term).OnlyEnforceIf(less)
            model.Add(build.term_vars[course.code] >= target_term).OnlyEnforceIf(less.Not())
            _equivalence(model, before, selected, less)
            before_terms.append(before)
        planned_courses = [course for course in request.courses if course.code not in request.completed]
        earned = request.completed_credits * 1000 + sum(course.credit_units * before for course, before in zip(planned_courses, before_terms))
        model.Add(earned >= expression.credits * 1000).OnlyEnforceIf(value)
        model.Add(earned <= expression.credits * 1000 - 1).OnlyEnforceIf(value.Not())
        return value
    if isinstance(expression, Predicate):
        value = model.NewBoolVar(f"predicate_{expression.kind}_{expression.value}")
        supplied = expression.value in (request.permissions if expression.kind == "permission" else request.placements)
        model.Add(value == int(supplied))
        if not supplied:
            build.invalid.append(f"unresolved {expression.kind} predicate {expression.value}")
        return value
    if isinstance(expression, (AllOf, CoRequisite)):
        value = model.NewBoolVar(f"all_{target_term.Name()}_{len(build.invalid)}")
        items = [_expr_bool(build, item, target_term, request, coreq=coreq or isinstance(expression, CoRequisite)) for item in expression.items]
        if items:
            model.AddBoolAnd(items).OnlyEnforceIf(value)
            model.AddBoolOr([item.Not() for item in items]).OnlyEnforceIf(value.Not())
        else:
            model.Add(value == 1)
        return value
    if isinstance(expression, AnyOf):
        value = model.NewBoolVar(f"any_{target_term.Name()}_{len(build.invalid)}")
        items = [_expr_bool(build, item, target_term, request, coreq=coreq) for item in expression.items]
        if items:
            model.AddBoolOr(items).OnlyEnforceIf(value)
            model.AddBoolAnd([item.Not() for item in items]).OnlyEnforceIf(value.Not())
        else:
            model.Add(value == 0)
        return value
    raise TypeError(f"unsupported AST node {type(expression)!r}")


def _build(request: PlanRequest) -> _Build:
    model = cp_model.CpModel()
    build = _Build(model, {}, {}, {}, {}, list(request.validate_input()))
    max_term = len(request.terms)
    for course in request.courses:
        term = model.NewIntVar(0, max_term, f"term_{course.code}")
        selected = model.NewBoolVar(f"selected_{course.code}")
        model.Add(term > 0).OnlyEnforceIf(selected)
        model.Add(term == 0).OnlyEnforceIf(selected.Not())
        build.term_vars[course.code] = term
        build.selected[course.code] = selected
        if course.code in request.excluded:
            model.Add(selected == 0)
        if course.code in request.pinned:
            assumption = model.NewBoolVar(f"assumption_pin_{course.code}")
            build.assumptions[assumption.Index()] = f"pin:{course.code}"
            model.Add(term == request.pinned[course.code]).OnlyEnforceIf(assumption)
            model.AddAssumption(assumption)
        allowed = sorted(course.available_terms or {term_spec.index for term_spec in request.terms})
        for index in range(1, max_term + 1):
            if index not in allowed:
                model.Add(term != index)
        if course.prerequisites is not None:
            eligible = _expr_bool(build, course.prerequisites, term, request)
            model.Add(eligible == 1).OnlyEnforceIf(selected)
        for coreq in course.co_requisites:
            if coreq in build.term_vars:
                model.Add(term == build.term_vars[coreq]).OnlyEnforceIf(selected, build.selected[coreq])
    term_members: dict[int, dict[str, cp_model.BoolVar]] = {}
    for term_spec in request.terms:
        assigned = []
        term_members[term_spec.index] = {}
        for course in request.courses:
            in_term = model.NewBoolVar(f"{course.code}_in_{term_spec.index}")
            model.Add(build.term_vars[course.code] == term_spec.index).OnlyEnforceIf(in_term)
            model.Add(build.term_vars[course.code] != term_spec.index).OnlyEnforceIf(in_term.Not())
            term_members[term_spec.index][course.code] = in_term
            assigned.append(course.credit_units * in_term)
        model.Add(sum(assigned) <= term_spec.max_credits * 1000)
        if term_spec.min_credits:
            model.Add(sum(assigned) >= term_spec.min_credits * 1000)
    build.term_members = term_members
    allocation_vars: dict[tuple[str, str], cp_model.BoolVar] = {}
    for group in request.requirements:
        allocations = []
        for course in request.courses:
            if course.code not in group.course_codes:
                continue
            allocation = model.NewBoolVar(f"allocate_{group.id}_{course.code}")
            allocation_vars[(group.id, course.code)] = allocation
            allocations.append((course, allocation))
            model.Add(allocation <= build.selected[course.code])
        if allocations:
            model.Add(sum(flag for _, flag in allocations) >= group.min_courses)
            if group.min_credits:
                model.Add(sum(course.credit_units * flag for course, flag in allocations) >= group.min_credits * 1000)
    for course in request.courses:
        flags = [allocation for (group_id, code), allocation in allocation_vars.items() if code == course.code and not next(group for group in request.requirements if group.id == group_id).allow_double_counting]
        if len(flags) > 1:
            model.Add(sum(flags) <= 1)
    return build


def _fallback_solve(request: PlanRequest, *, alternatives: int) -> tuple[PlanResult, ...]:
    from boiler_reviews.planning.oracle import enumerate_optimum

    oracle = enumerate_optimum(request, max_assignments=100_000)
    if oracle.feasible:
        status = "unknown" if oracle.truncated else "optimal"
        validation = validate_plan(request, oracle.assignment or {})
        return (PlanResult(status, oracle.assignment or {}, oracle.objective_value, float(oracle.objective_value or 0), ("CP-SAT native extension unavailable; bounded independent oracle used",), validator=validation),)
    status = "unknown" if oracle.truncated else "infeasible"
    diagnostic = explain_infeasibility(request, base_assignment={})
    diagnostics = diagnostic.assumption_core + ("CP-SAT native extension unavailable; bounded oracle found no solution" if oracle.truncated else diagnostic.limitation or "",)
    return (PlanResult(status, {}, None, None, diagnostics),)


def solve(request: PlanRequest, *, alternatives: int = 1) -> tuple[PlanResult, ...]:
    if cp_model is None:
        return _fallback_solve(request, alternatives=alternatives)
    build = _build(request)
    if build.invalid:
        result = PlanResult("invalid_model", {}, None, None, tuple(build.invalid))
        return (result,)
    # CP-SAT uses integer objectives. Weighted objective values are documented in
    # the planner contract and deliberately bounded by course count.
    term_score = sum(((len(request.terms) + 1) * build.selected[course.code] - build.term_vars[course.code]) * course.credit_units for course in request.courses)
    if request.objective == "balanced_workload":
        max_workload = build.model.NewIntVar(0, 1_000_000, "max_workload")
        for term_spec in request.terms:
            workload = sum(course.workload_hours * build.term_members[term_spec.index][course.code] for course in request.courses)
            build.model.Add(max_workload >= workload)
        build.model.Minimize(max_workload)
    elif request.objective == "preference_satisfaction":
        build.model.Maximize(sum(course.preference_score * build.selected[course.code] for course in request.courses))
    else:
        build.model.Maximize(term_score)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = request.time_limit_seconds
    solver.parameters.random_seed = request.random_seed
    solver.parameters.num_search_workers = 1
    results: list[PlanResult] = []
    for alternative_index in range(max(1, alternatives)):
        status = solver.Solve(build.model)
        status_name = {cp_model.OPTIMAL: "optimal", cp_model.FEASIBLE: "feasible", cp_model.INFEASIBLE: "infeasible", cp_model.UNKNOWN: "unknown", cp_model.MODEL_INVALID: "invalid_model"}.get(status, "unknown")
        assignment = {course.code: solver.Value(build.term_vars[course.code]) for course in request.courses} if status in {cp_model.OPTIMAL, cp_model.FEASIBLE} else {}
        validation = validate_plan(request, assignment) if assignment else None
        if validation is not None and not validation.valid:
            results.append(PlanResult("invalid_model", assignment, int(solver.ObjectiveValue()), solver.BestObjectiveBound(), validation.violations, validator=validation))
            break
        core = tuple(build.assumptions[index] for index in solver.SufficientAssumptionsForInfeasibility() if index in build.assumptions) if status == cp_model.INFEASIBLE else ()
        diagnostic = explain_infeasibility(request, base_assignment=assignment) if status == cp_model.INFEASIBLE else None
        results.append(PlanResult(status, assignment, int(solver.ObjectiveValue()) if status in {cp_model.OPTIMAL, cp_model.FEASIBLE} else None, solver.BestObjectiveBound(), tuple(diagnostic.assumption_core if diagnostic else ()), core or (diagnostic.limitation if diagnostic else "",)))
        if alternative_index + 1 < alternatives and status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            literals = [build.term_vars[course.code] != assignment[course.code] for course in request.courses]
            build.model.AddBoolOr([literal for literal in literals])
    return tuple(results)
