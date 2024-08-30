from boiler_reviews.reviews.ranking import CourseCandidate, RankingPreferences, rank_courses


def test_ranking_returns_factors_and_never_ranks_infeasible_as_feasible():
    candidates = [
        CourseCandidate("a", "CS101", "Foundations", True, 4.5, 12, 8.0, .9, .8),
        CourseCandidate("b", "CS201", "Advanced", False, 5.0, 50, 4.0, 1.0, 1.0),
    ]
    ranked = rank_courses(candidates, RankingPreferences())
    assert ranked[0].candidate.code == "CS101"
    assert ranked[0].score is not None
    assert ranked[0].factors["evidence_quality_and_rating"] > 0
    assert ranked[1].score is None
