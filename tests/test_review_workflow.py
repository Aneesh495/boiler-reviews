from __future__ import annotations

from sqlalchemy import select

from boiler_reviews.db.models import Account, CourseAggregate


def review_payload(client, app):
    return {
        "course_id": app.config["TEST_COURSE_ID"],
        "term_id": app.config["TEST_TERM_ID"],
        "professor": "Dr. Ada",
        "difficulty": 3,
        "workload_hours": 6,
        "overall": 5,
        "would_recommend": True,
        "comment": "Clear and rigorous.",
    }


def test_owner_submission_and_moderator_publication_update_aggregate(client, app):
    assert client.post("/api/v1/auth/register", json={"email": "student@test.invalid", "password": "a-long-test-password", "display_name": "Student"}).status_code == 201
    created = client.post("/api/v1/reviews", json=review_payload(client, app))
    assert created.status_code == 201
    review_id = created.json["id"]
    assert client.get("/api/v1/reviews").json["total"] == 0
    assert client.post(f"/api/v1/reviews/{review_id}/submit").json["status"] == "submitted"

    with app.config["TEST_FACTORY"]() as session:
        account = session.scalar(select(Account).where(Account.email == "student@test.invalid"))
        assert account is not None
        account.roles_json = ["moderator"]
        session.commit()

    published = client.post(f"/api/v1/moderation/reviews/{review_id}", json={"decision": "published", "reason": "Policy checks passed"})
    assert published.status_code == 200
    assert published.json["status"] == "published"
    assert client.get("/api/v1/reviews").json["total"] == 1

    with app.config["TEST_FACTORY"]() as session:
        aggregate = session.scalar(select(CourseAggregate))
        assert aggregate is not None
        assert aggregate.review_count == 1
        assert aggregate.sum_overall == 5


def test_published_revision_remains_public_while_edit_is_pending(client, app):
    client.post("/api/v1/auth/register", json={"email": "owner@test.invalid", "password": "a-long-test-password", "display_name": "Owner"})
    response = client.post("/api/v1/reviews", json=review_payload(client, app))
    review_id = response.json["id"]
    client.post(f"/api/v1/reviews/{review_id}/submit")
    with app.config["TEST_FACTORY"]() as session:
        account = session.scalar(select(Account).where(Account.email == "owner@test.invalid"))
        assert account is not None
        account.roles_json = ["moderator"]
        session.commit()
    client.post(f"/api/v1/moderation/reviews/{review_id}", json={"decision": "published", "reason": "approved"})
    edited = dict(review_payload(client, app))
    edited["overall"] = 2
    edited["revision"] = 1
    changed = client.patch(f"/api/v1/reviews/{review_id}", json=edited)
    assert changed.status_code == 200
    assert changed.json["status"] == "submitted"
    public = client.get("/api/v1/reviews").json
    assert public["total"] == 1
    assert public["items"][0]["content"]["overall"] == 5
