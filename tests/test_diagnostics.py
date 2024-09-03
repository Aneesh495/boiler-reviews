from boiler_reviews.planning.diagnostics import explain_infeasibility
from boiler_reviews.planning.model import CourseSpec, PlanRequest, TermSpec


def test_diagnostic_labels_checked_relaxation_and_limitation():
    request = PlanRequest(courses=(CourseSpec("A", 1000, frozenset({1})),), terms=(TermSpec("one", 1, 0, 1),), pinned={"A": 1})
    diagnostic = explain_infeasibility(request, base_assignment={"A": 0})
    assert "pin:A" in diagnostic.assumption_core
    assert diagnostic.relaxations[0].checked is True
    assert diagnostic.limitation is not None
