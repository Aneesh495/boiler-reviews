from __future__ import annotations

from boiler_reviews.planning.api import plan_result_payload, request_from_json
from boiler_reviews.planning.solver import solve


def payload():
    return {
        "terms": [{"id": "fall", "index": 1, "max_credits": 3}, {"id": "spring", "index": 2, "max_credits": 3}],
        "courses": [{"code": "AA101", "credits": 3, "available_terms": [1], "requirement_groups": ["core"]}, {"code": "BB101", "credits": 3, "available_terms": [2], "prerequisites": {"type": "course", "code": "AA101"}, "requirement_groups": ["core"]}],
        "requirements": [{"id": "core", "label": "Core", "course_codes": ["AA101", "BB101"], "min_courses": 2, "min_credits": 6}],
    }


def test_typed_plan_api_contract_round_trip():
    request = request_from_json(payload())
    result = solve(request)[0]
    encoded = plan_result_payload(result)
    assert encoded["status"] in {"optimal", "feasible", "unknown"}
    assert encoded["assignment"]["AA101"] == 1
