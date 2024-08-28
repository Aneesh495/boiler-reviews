from __future__ import annotations

import random

from boiler_reviews.catalog.parser import parse_prerequisites


def test_one_thousand_generated_expressions_are_total():
    random.seed(20261001)
    courses = [f"CS{index:03d}" for index in range(1, 40)]
    for _ in range(1000):
        left, right = random.sample(courses, 2)
        source = f"({left} OR {right}) AND CREDITS>={random.choice([15, 30, 60])}"
        result = parse_prerequisites(source)
        assert result.status == "parsed"
        assert result.ast is not None
