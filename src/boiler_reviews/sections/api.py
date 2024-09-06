from __future__ import annotations

from typing import Any

from boiler_reviews.sections.scheduler import Meeting, SectionOption


def meeting_from_json(value: dict[str, Any]) -> Meeting:
    return Meeting(
        weekday=int(value.get("weekday", 0)),
        start_minute=int(value["start_minute"]) if value.get("start_minute") is not None else None,
        end_minute=int(value["end_minute"]) if value.get("end_minute") is not None else None,
        timezone=str(value.get("timezone", "America/Indiana/Indianapolis")),
        location=str(value["location"]) if value.get("location") else None,
        known=bool(value.get("known", True)),
    )


def option_from_json(value: dict[str, Any]) -> SectionOption:
    return SectionOption(
        course_code=str(value["course_code"]),
        term_index=int(value["term_index"]),
        section_id=str(value["section_id"]),
        label=str(value.get("label", value["section_id"])),
        meetings=tuple(meeting_from_json(item) for item in value.get("meetings", [])),
        linked_group=str(value["linked_group"]) if value.get("linked_group") else None,
        capacity=int(value["capacity"]) if value.get("capacity") is not None else None,
        capacity_observed_at=str(value["capacity_observed_at"]) if value.get("capacity_observed_at") else None,
        asynchronous=bool(value.get("asynchronous", False)),
    )
