from __future__ import annotations

from boiler_reviews.catalog.ast import AllOf, AnyOf, CoRequisite, GradeAtLeast
from boiler_reviews.catalog.graph import PrerequisiteGraph, evaluate
from boiler_reviews.catalog.parser import parse_prerequisites


def test_parser_preserves_and_or_grade_and_corequisite():
    result = parse_prerequisites("CS101 GRADE>=B AND (MA101 OR MA102)")
    assert result.status == "parsed"
    assert isinstance(result.ast, AllOf)
    assert any(isinstance(item, AnyOf) for item in result.ast.items)
    assert any(isinstance(item, GradeAtLeast) for item in result.ast.items)
    coreq = parse_prerequisites("COREQ(CS201, CS202)")
    assert isinstance(coreq.ast, CoRequisite)
    assert len(coreq.ast.items) == 2


def test_parser_keeps_unsupported_text_unresolved():
    result = parse_prerequisites("department approval and placement by advisor")
    assert result.status == "unsupported"
    assert result.ast is None


def test_graph_reports_unknown_and_strict_cycle():
    first = parse_prerequisites("CS102")
    second = parse_prerequisites("CS101")
    graph = PrerequisiteGraph({"CS101": first.ast, "CS102": second.ast})
    assert graph.unknown_references({"CS101", "CS102"}) == set()
    assert graph.strict_cycles()
    assert graph.dependency_path("CS101", "CS102") == ("CS101", "CS102")


def test_or_and_permission_semantics_are_explicit():
    expression = parse_prerequisites("CS101 OR PERMISSION(instructor)").ast
    assert expression is not None
    assert evaluate(expression, completed=set(), in_term=set(), earned_credits=0).state == "unknown"
    assert evaluate(expression, completed={"CS101"}, in_term=set(), earned_credits=0).state == "satisfied"
