from boiler_reviews.reviews.stats import rating_summary


def test_zero_reviews_are_missing_not_zero():
    summary = rating_summary(0, 0)
    assert summary.mean is None
    assert summary.warning == "No published review evidence"


def test_sparse_summary_is_shrunk_and_warned():
    summary = rating_summary(1, 5)
    assert summary.mean < 5
    assert summary.warning == "Small sample"
    assert summary.lower is not None
    assert summary.upper is not None
