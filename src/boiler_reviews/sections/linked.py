from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from boiler_reviews.sections.scheduler import SectionOption


@dataclass(frozen=True, slots=True)
class LinkedSectionGroup:
    group_id: str
    course_code: str
    section_ids: tuple[str, ...]
    required_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LinkedSectionValidation:
    valid: bool
    missing_groups: tuple[str, ...]
    duplicate_groups: tuple[str, ...]
    explanations: tuple[str, ...]


def validate_linked_sections(options: Iterable[SectionOption], groups: Iterable[LinkedSectionGroup]) -> LinkedSectionValidation:
    selected = list(options); by_group: dict[str, list[SectionOption]] = {}
    for option in selected:
        if option.linked_group:
            by_group.setdefault(option.linked_group, []).append(option)
    missing=[]; duplicates=[]; explanations=[]
    for group in groups:
        values=by_group.get(group.group_id, [])
        if len(values) < len(group.required_kinds):
            missing.append(group.group_id); explanations.append(f"{group.course_code} needs linked components {', '.join(group.required_kinds)}")
        if len(values) > len(group.required_kinds):
            duplicates.append(group.group_id); explanations.append(f"{group.course_code} has too many sections in linked group {group.group_id}")
    return LinkedSectionValidation(not missing and not duplicates, tuple(missing), tuple(duplicates), tuple(explanations))
