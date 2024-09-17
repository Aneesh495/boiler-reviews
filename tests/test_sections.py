from __future__ import annotations

from boiler_reviews.sections.scheduler import (
    Meeting,
    SectionOption,
    choose_sections,
    export_icalendar,
    validate_schedule,
)


def meeting(start, end, weekday=0, known=True):
    return Meeting(weekday, start, end, "America/Indiana/Indianapolis", known=known)


def test_half_open_boundary_and_multi_meeting_conflicts():
    left = SectionOption("CS101", 1, "A", "Lecture A", (meeting(600, 660), meeting(720, 780, weekday=2)))
    right = SectionOption("MA101", 1, "B", "Lecture B", (meeting(660, 720),))
    assert validate_schedule({"CS101": left, "MA101": right}).status == "valid"
    conflict = SectionOption("MA101", 1, "C", "Lecture C", (meeting(650, 700),))
    assert validate_schedule({"CS101": left, "MA101": conflict}).status == "invalid"


def test_unknown_time_is_warning_not_guaranteed_free():
    option = SectionOption("CS101", 1, "ASYNC", "Online", (meeting(None, None, known=False),))
    result = validate_schedule({"CS101": option})
    assert result.status == "valid"
    assert result.unknown_meetings


def test_section_search_and_calendar_export():
    options = [
        SectionOption("CS101", 1, "A", "Lecture A", (meeting(600, 660),)),
        SectionOption("MA101", 1, "B", "Lecture B", (meeting(600, 660),)),
        SectionOption("MA101", 1, "C", "Lecture C", (meeting(660, 720),)),
    ]
    result = choose_sections({"CS101": 1, "MA101": 1}, options)
    assert result.status == "feasible"
    assert result.selected["MA101"].section_id == "C"
    calendar = export_icalendar(result.selected, term_starts_on="2026-08-24", term_ends_on="2026-12-19")
    assert "BEGIN:VEVENT" in calendar
    assert "RRULE:FREQ=WEEKLY;UNTIL=20261214T235959Z" in calendar
    assert "TZID=America/Indiana/Indianapolis" in calendar
