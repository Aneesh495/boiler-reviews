from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from boiler_reviews.catalog.schema import CatalogCourse, CatalogDocument


@dataclass(frozen=True, slots=True)
class CourseImpact:
    code: str
    change_types: tuple[str, ...]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    saved_plans: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CatalogImpact:
    from_version: str
    to_version: str
    changes: tuple[CourseImpact, ...]

    @property
    def affected_courses(self) -> tuple[str, ...]:
        return tuple(change.code for change in self.changes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "affected_courses": list(self.affected_courses),
            "changes": [
                {"code": change.code, "change_types": list(change.change_types), "before": change.before, "after": change.after, "saved_plans": list(change.saved_plans)}
                for change in self.changes
            ],
        }


def _course_value(course: CatalogCourse) -> dict[str, Any]:
    return {"code": course.code, "stable_code": course.stable_code or course.code, "title": course.title, "credits": course.credits, "prerequisites": course.prerequisites, "availability": course.availability}


def compare_catalogs(before: CatalogDocument, after: CatalogDocument, *, saved_plan_courses: dict[str, tuple[str, ...]] | None = None) -> CatalogImpact:
    saved_plan_courses = saved_plan_courses or {}
    left = {course.stable_code or course.code: course for course in before.courses}
    right = {course.stable_code or course.code: course for course in after.courses}
    changes: list[CourseImpact] = []
    for stable_code in sorted(set(left) | set(right)):
        old, new = left.get(stable_code), right.get(stable_code)
        change_types: list[str] = []
        if old is None:
            change_types.append("added")
        elif new is None:
            change_types.append("removed")
        else:
            if old.code != new.code or old.title != new.title:
                change_types.append("renamed")
            if old.credits != new.credits:
                change_types.append("credits")
            if old.prerequisites != new.prerequisites:
                change_types.append("prerequisite_semantics")
            if old.availability != new.availability:
                change_types.append("availability")
        if change_types:
            display_code = (new or old).code  # type: ignore[union-attr]
            changes.append(CourseImpact(display_code, tuple(change_types), _course_value(old) if old else None, _course_value(new) if new else None, tuple(sorted(plan_id for plan_id, codes in saved_plan_courses.items() if stable_code in codes))))
    return CatalogImpact(before.version, after.version, tuple(changes))


def revalidate_saved_plan(impact: CatalogImpact, plan_id: str, selected_codes: set[str]) -> dict[str, Any]:
    affected = {change.code for change in impact.changes if plan_id in change.saved_plans}
    selected_affected = sorted(affected & selected_codes)
    return {"plan_id": plan_id, "catalog_from": impact.from_version, "catalog_to": impact.to_version, "status": "needs_review" if selected_affected else "unchanged", "affected_selected_courses": selected_affected, "reason": "Catalog semantics changed for a selected course; historical plan remains immutable." if selected_affected else "No selected course changed."}
