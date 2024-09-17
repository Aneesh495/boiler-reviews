from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Meeting:
    weekday: int
    start_minute: int | None
    end_minute: int | None
    timezone: str
    location: str | None = None
    known: bool = True

    def overlaps(self, other: Meeting) -> bool:
        if not self.known or not other.known or self.start_minute is None or other.start_minute is None or self.end_minute is None or other.end_minute is None:
            return False
        return self.weekday == other.weekday and self.start_minute < other.end_minute and other.start_minute < self.end_minute


@dataclass(frozen=True, slots=True)
class SectionOption:
    course_code: str
    term_index: int
    section_id: str
    label: str
    meetings: tuple[Meeting, ...] = ()
    linked_group: str | None = None
    capacity: int | None = None
    capacity_observed_at: str | None = None
    asynchronous: bool = False

    @property
    def has_unknown_meetings(self) -> bool:
        return not self.asynchronous and any(not meeting.known for meeting in self.meetings)


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    status: str
    selected: dict[str, SectionOption]
    conflicts: tuple[str, ...] = ()
    unknown_meetings: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


def _conflicts(left: SectionOption, right: SectionOption) -> bool:
    return any(first.overlaps(second) for first in left.meetings for second in right.meetings)


def validate_schedule(selected: dict[str, SectionOption], *, expected_terms: dict[str, int] | None = None, blocked: tuple[Meeting, ...] = ()) -> ScheduleResult:
    conflicts: list[str] = []
    unknown: list[str] = []
    expected_terms = expected_terms or {}
    for code, option in selected.items():
        if expected_terms.get(code, option.term_index) != option.term_index:
            conflicts.append(f"{code} section {option.section_id} is in term {option.term_index}, not the planned term")
        if option.has_unknown_meetings:
            unknown.append(f"{code} {option.label} has unknown meeting time")
        if any(_conflicts(option, blocked_item) for blocked_item in blocked):
            conflicts.append(f"{code} {option.label} conflicts with an unavailable time")
    values = list(selected.values())
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            if _conflicts(left, right):
                conflicts.append(f"{left.course_code} {left.label} conflicts with {right.course_code} {right.label}")
    return ScheduleResult("valid" if not conflicts else "invalid", selected, tuple(dict.fromkeys(conflicts)), tuple(dict.fromkeys(unknown)), ("Unknown meeting times were not assumed conflict-free." if unknown else "",))


def choose_sections(
    planned_courses: dict[str, int],
    options: Iterable[SectionOption],
    *,
    blocked: tuple[Meeting, ...] = (),
) -> ScheduleResult:
    by_course: dict[str, list[SectionOption]] = {code: [] for code in planned_courses}
    for option in options:
        if option.course_code in by_course and option.term_index == planned_courses[option.course_code]:
            by_course[option.course_code].append(option)
    missing = [code for code, values in by_course.items() if not values]
    if missing:
        return ScheduleResult("infeasible", {}, tuple(f"No section option for {code}" for code in missing))
    ordered = sorted(by_course, key=lambda code: len(by_course[code]))
    selected: dict[str, SectionOption] = {}

    def search(index: int) -> bool:
        if index == len(ordered):
            return True
        code = ordered[index]
        for option in sorted(by_course[code], key=lambda value: (value.has_unknown_meetings, value.section_id)):
            if any(_conflicts(option, existing) for existing in selected.values()):
                continue
            if any(_conflicts(option, blocked_item) for blocked_item in blocked):
                continue
            selected[code] = option
            if search(index + 1):
                return True
            selected.pop(code)
        return False

    if not search(0):
        return ScheduleResult("infeasible", {}, ("No conflict-free section combination satisfies the selected courses",))
    result = validate_schedule(selected, expected_terms=planned_courses, blocked=blocked)
    return ScheduleResult("feasible", result.selected, result.conflicts, result.unknown_meetings, result.diagnostics)


def _format_time(minute: int) -> str:
    return f"{minute // 60:02d}{minute % 60:02d}00"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def export_icalendar(selected: dict[str, SectionOption], *, term_starts_on: str, term_ends_on: str, calendar_name: str = "Boiler Reviews schedule") -> str:
    start = date.fromisoformat(term_starts_on)
    end = date.fromisoformat(term_ends_on)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Boiler Reviews//Academic Planner//EN", f"X-WR-CALNAME:{_escape(calendar_name)}"]
    for course_code, option in sorted(selected.items()):
        for index, meeting in enumerate(option.meetings):
            if not meeting.known or meeting.start_minute is None or meeting.end_minute is None:
                continue
            first = start.fromordinal(start.toordinal() + ((meeting.weekday - start.weekday()) % 7))
            last = date.fromordinal(end.toordinal() - ((end.weekday() - meeting.weekday) % 7))
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{_escape(option.section_id)}-{index}@boiler-reviews",
                f"SUMMARY:{_escape(course_code)} { _escape(option.label) }",
                f"DTSTART;TZID={meeting.timezone}:{first.strftime('%Y%m%d')}T{_format_time(meeting.start_minute)}",
                f"DTEND;TZID={meeting.timezone}:{first.strftime('%Y%m%d')}T{_format_time(meeting.end_minute)}",
                f"RRULE:FREQ=WEEKLY;UNTIL={last.strftime('%Y%m%d')}T235959Z",
                f"LOCATION:{_escape(meeting.location or 'TBD')}",
                "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
