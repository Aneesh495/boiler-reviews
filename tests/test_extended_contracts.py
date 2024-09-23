from __future__ import annotations

import pytest

from boiler_reviews.catalog.adapters import (
    CatalogAdapterError,
    CsvCatalogAdapter,
)
from boiler_reviews.catalog.impact import compare_catalogs, revalidate_saved_plan
from boiler_reviews.catalog.schema import CatalogDocument
from boiler_reviews.identity.rate_limit import TokenBucketLimiter
from boiler_reviews.planning.api import precheck_payload
from boiler_reviews.planning.model import CourseSpec, PlanRequest, RequirementGroup, TermSpec
from boiler_reviews.planning.prechecks import precheck
from boiler_reviews.sections.linked import LinkedSectionGroup, validate_linked_sections
from boiler_reviews.sections.scheduler import Meeting, SectionOption


def test_csv_adapter_retains_provenance_and_rejects_bad_headers():
    payload = "code,title,credits,prerequisites,availability\nCS101,Foundations,3,NONE,Fall|Spring\n"
    document, provenance = CsvCatalogAdapter().read(payload, source_uri="file:///tmp/catalog.csv")
    assert document.courses[0].code == "CS101"
    assert provenance.source_kind == "documented_csv"
    with pytest.raises(CatalogAdapterError):
        CsvCatalogAdapter().read("title,credits\nBad,3\n", source_uri="fixture://bad")


def test_catalog_impact_marks_selected_saved_plan():
    before = CatalogDocument.model_validate({"institution_code":"XX","institution_name":"X","version":"1","courses":[{"code":"CS101","title":"Foundations","credits":3,"prerequisites":"NONE"}]})
    after = CatalogDocument.model_validate({"institution_code":"XX","institution_name":"X","version":"2","courses":[{"code":"CS101","title":"Foundations","credits":4,"prerequisites":"CREDITS>=3"}]})
    impact = compare_catalogs(before, after, saved_plan_courses={"plan-1": ("CS101",)})
    assert impact.affected_courses == ("CS101",)
    assert revalidate_saved_plan(impact, "plan-1", {"CS101"})["status"] == "needs_review"


def test_token_bucket_denies_until_refill():
    limiter = TokenBucketLimiter(capacity=1, refill_per_second=1)
    assert limiter.consume("account", now=0).allowed
    denied = limiter.consume("account", now=0)
    assert not denied.allowed
    assert limiter.consume("account", now=1).allowed


def test_precheck_and_linked_section_contracts():
    request = PlanRequest(courses=(CourseSpec("CS101", 3000, frozenset({1}), requirement_groups=frozenset({"core"})),), terms=(TermSpec("fall", 1, 0, 3),), requirements=(RequirementGroup("core", "Core", frozenset({"CS101"}), min_courses=1, min_credits=3),))
    assert precheck(request).valid
    assert precheck_payload(request)["valid"]
    option = SectionOption("CS101", 1, "lecture", "Lecture", (Meeting(0, 600, 660, "America/Indiana/Indianapolis"),), linked_group="lab-set")
    result = validate_linked_sections((option,), (LinkedSectionGroup("lab-set", "CS101", ("lecture", "lab"), ("lecture", "lab")),))
    assert not result.valid
    assert result.missing_groups == ("lab-set",)
