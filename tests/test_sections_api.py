from __future__ import annotations

from boiler_reviews.sections.api import option_from_json


def test_section_json_preserves_unknown_meeting_and_capacity_observation():
    option = option_from_json({"course_code": "CS101", "term_index": 1, "section_id": "L1", "label": "Lecture", "capacity": 30, "capacity_observed_at": "2026-09-30T12:00:00Z", "meetings": [{"weekday": 1, "start_minute": None, "end_minute": None, "known": False}]})
    assert option.capacity == 30
    assert option.has_unknown_meetings
