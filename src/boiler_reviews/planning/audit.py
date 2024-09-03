from __future__ import annotations

from dataclasses import dataclass

from boiler_reviews.planning.model import RequirementGroup


@dataclass(frozen=True, slots=True)
class AuditRequirement:
    group_id: str
    label: str
    state: str
    satisfied_codes: tuple[str, ...]
    pending_codes: tuple[str, ...]
    missing_courses: int
    missing_credits: int
    explanation: str


@dataclass(frozen=True, slots=True)
class DegreeAudit:
    requirements: tuple[AuditRequirement, ...]
    earned_credits: int
    proposed_credits: int
    unknown_rules: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return all(item.state == "satisfied" for item in self.requirements) and not self.unknown_rules


def audit_degree(
    requirements: tuple[RequirementGroup, ...],
    *,
    completed: frozenset[str],
    completed_credits: int,
    proposed_by_term: dict[int, tuple[str, ...]] | None = None,
    credit_by_code: dict[str, int] | None = None,
) -> DegreeAudit:
    proposed_by_term = proposed_by_term or {}
    credit_by_code = credit_by_code or {}
    proposed = {code for courses in proposed_by_term.values() for code in courses}
    all_known = completed | proposed
    allocations: dict[str, str] = {}
    result: list[AuditRequirement] = []
    unknown: list[str] = []
    for group in requirements:
        if group.unknown:
            unknown.append(group.label)
            result.append(AuditRequirement(group.id, group.label, "unknown", (), (), group.min_courses, group.min_credits, "Institutional rule is unresolved in the imported degree version."))
            continue
        eligible_completed = sorted((completed & group.course_codes) - set(allocations))
        eligible_proposed = sorted((proposed & group.course_codes) - set(allocations))
        selected_completed = eligible_completed[: group.min_courses]
        remaining_slots = max(0, group.min_courses - len(selected_completed))
        selected_proposed = eligible_proposed[:remaining_slots]
        selected = selected_completed + selected_proposed
        if not group.allow_double_counting:
            for code in selected:
                allocations[code] = group.id
        earned = sum(credit_by_code.get(code, 0) for code in selected_completed)
        planned = sum(credit_by_code.get(code, 0) for code in selected_proposed)
        missing_courses = max(0, group.min_courses - len(selected))
        missing_credits = max(0, group.min_credits - earned - planned)
        if missing_courses or missing_credits:
            state = "pending" if selected_proposed else "unsatisfied"
        elif selected_proposed and not selected_completed:
            state = "pending"
        else:
            state = "satisfied"
        result.append(
            AuditRequirement(
                group.id,
                group.label,
                state,
                tuple(selected_completed),
                tuple(selected_proposed),
                missing_courses,
                missing_credits,
                f"{len(selected_completed)} completed and {len(selected_proposed)} planned course(s) allocated to this requirement; double counting is {'allowed' if group.allow_double_counting else 'not allowed'}.",
            )
        )
    return DegreeAudit(tuple(result), completed_credits, sum(credit_by_code.get(code, 0) for code in proposed), tuple(unknown))
