from boiler_reviews.planning.audit import audit_degree
from boiler_reviews.planning.model import RequirementGroup


def test_degree_audit_allocates_without_double_counting():
    requirements = (
        RequirementGroup("core", "Core", frozenset({"A", "B"}), min_courses=1),
        RequirementGroup("elective", "Elective", frozenset({"A", "C"}), min_courses=1),
    )
    audit = audit_degree(requirements, completed=frozenset({"A"}), completed_credits=3, credit_by_code={"A": 3, "C": 3})
    assert audit.requirements[0].state == "satisfied"
    assert audit.requirements[1].state == "unsatisfied"


def test_future_course_is_pending_not_completed():
    requirement = RequirementGroup("core", "Core", frozenset({"A"}), min_courses=1)
    audit = audit_degree((requirement,), completed=frozenset(), completed_credits=0, proposed_by_term={1: ("A",)}, credit_by_code={"A": 3})
    assert audit.requirements[0].state == "pending"
