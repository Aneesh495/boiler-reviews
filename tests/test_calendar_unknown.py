from boiler_reviews.sections.scheduler import Meeting, SectionOption, export_icalendar


def test_unknown_intervals_are_not_fabricated_in_calendar():
    option = SectionOption("CS101", 1, "unknown", "TBD", (Meeting(0, None, None, "America/Indiana/Indianapolis", known=False),))
    calendar = export_icalendar({"CS101": option}, term_starts_on="2026-08-24", term_ends_on="2026-12-19")
    assert "BEGIN:VEVENT" not in calendar
    assert "BEGIN:VCALENDAR" in calendar
