from boiler_reviews.sections.scheduler import SectionOption, choose_sections


def test_no_options_is_infeasible():
    result = choose_sections({"CS101": 2}, [SectionOption("CS101", 1, "A", "Wrong term")])
    assert result.status == "infeasible"
    assert "CS101" in result.conflicts[0]
