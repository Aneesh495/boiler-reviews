from __future__ import annotations

from boiler_reviews.reviews.stats import course_statistics


def test_statistics_distinguish_missing_workload_and_include_quantiles(app):
    with app.config["TEST_FACTORY"]() as session:
        result = course_statistics(session, course_id=app.config["TEST_COURSE_ID"])
        assert result.review_count == 0
        assert result.overall.mean is None
        assert result.workload_quantiles_hours is None
