from __future__ import annotations

from sqlalchemy import select

from boiler_reviews.db.models import Account


def _review(client, app):
    client.post("/api/v1/auth/register", json={"email": "author@moderation.test", "password": "a-long-test-password", "display_name": "Author"})
    response = client.post("/api/v1/reviews", json={"course_id": app.config["TEST_COURSE_ID"], "term_id": app.config["TEST_TERM_ID"], "professor": "Dr. Review", "difficulty": 3, "workload_hours": 4, "overall": 4, "would_recommend": True})
    review_id = response.json["id"]
    client.post(f"/api/v1/reviews/{review_id}/submit")
    return review_id


def test_report_vote_and_moderation_queue_are_authenticated(client, app):
    review_id = _review(client, app)
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/register", json={"email": "reader@moderation.test", "password": "a-long-test-password", "display_name": "Reader"})
    vote = client.post(f"/api/v1/reviews/{review_id}/helpful", json={"helpful": True})
    report = client.post(f"/api/v1/reviews/{review_id}/report", json={"reason": "Needs a source check"})
    assert vote.status_code == 200
    assert report.status_code == 201
    with app.config["TEST_FACTORY"]() as session:
        account = session.scalar(select(Account).where(Account.email == "reader@moderation.test"))
        assert account is not None
        account.roles_json = ["moderator"]
        session.commit()
    queue = client.get("/api/v1/moderation/queue")
    assert queue.status_code == 200
    assert queue.json["items"][0]["open_reports"] == 1
