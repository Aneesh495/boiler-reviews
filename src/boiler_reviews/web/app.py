from __future__ import annotations

import logging
import os
import secrets
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from flask import Flask, g, jsonify, render_template, request, session
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from boiler_reviews.common.errors import ConflictError, DomainError, NotFoundError, PermissionDenied, ValidationError
from boiler_reviews.config import Settings, project_root
from boiler_reviews.db.health import readiness
from boiler_reviews.db.migrate import upgrade
from boiler_reviews.db.models import Account, Course, CourseAggregate, Review, ReviewRevision, Term
from boiler_reviews.db.session import build_engine, build_session_factory, session_scope
from boiler_reviews.identity.service import authenticate, register_account, to_authenticated
from boiler_reviews.reviews.moderation import moderation_queue, report_review, vote_helpful
from boiler_reviews.reviews.ranking import CourseCandidate, RankingPreferences, rank_courses
from boiler_reviews.reviews.service import ReviewInput, create_review, edit_review, moderate_review, submit_review
from boiler_reviews.reviews.stats import course_statistics, rating_summary, reconcile

F = TypeVar("F", bound=Callable[..., Any])


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings.from_env()
    root = project_root()
    settings.ensure_local_directories(root)
    engine = build_engine(settings)
    upgrade(engine)
    factory = build_session_factory(engine)

    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))
    app.config.update(
        SECRET_KEY=settings.secret_key,
        JSON_SORT_KEYS=False,
        SETTINGS=settings,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.environment == "production",
        ENGINE=engine,
        SESSION_FACTORY=factory,
    )
    if settings.csrf_enabled:
        csrf = CSRFProtect(app)
        app.extensions["csrf"] = csrf

    logger = logging.getLogger("boiler_reviews.http")

    @app.before_request
    def request_context() -> None:
        g.request_id = request.headers.get("X-Request-ID", secrets.token_hex(8))

    @app.after_request
    def response_context(response: Any) -> Any:
        response.headers["X-Request-ID"] = g.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.errorhandler(DomainError)
    def handle_domain_error(error: DomainError) -> tuple[Any, int]:
        status = 400
        if isinstance(error, NotFoundError):
            status = 404
        elif isinstance(error, (ConflictError, PermissionDenied)):
            status = 409 if isinstance(error, ConflictError) else 403
        payload: dict[str, Any] = {"error": {"code": error.__class__.__name__, "message": str(error)}}
        if isinstance(error, ValidationError):
            payload["error"]["fields"] = error.fields
        return jsonify(payload), status

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[Any, int]:
        logger.exception("request failed", extra={"request_id": g.get("request_id")})
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500

    def db_session() -> Session:
        return factory()

    def current_account(session_db: Session) -> Account | None:
        account_id = session.get("account_id")
        return session_db.get(Account, account_id) if account_id else None

    def require_account(function: F) -> F:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with session_scope(factory) as session_db:
                account = current_account(session_db)
                if account is None:
                    return jsonify({"error": {"code": "authentication_required", "message": "Sign in first."}}), 401
                g.account_id = account.id
            return function(*args, **kwargs)
        return wrapped  # type: ignore[return-value]

    def json_body() -> dict[str, Any]:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValidationError("A JSON object is required.")
        return body

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok", "service": "boiler-reviews", "version": "0.1.0"})

    @app.get("/ready")
    def ready() -> Any:
        with session_scope(factory) as session_db:
            payload = readiness(session_db)
        return jsonify(payload), 200 if payload["status"] == "ready" else 503

    @app.get("/api/v1/csrf")
    def csrf_token() -> Any:
        from flask_wtf.csrf import generate_csrf
        return jsonify({"csrf_token": generate_csrf()})

    @app.post("/api/v1/auth/register")
    def register() -> Any:
        body = json_body()
        with session_scope(factory) as session_db:
            account = register_account(
                session_db,
                email=str(body.get("email", "")),
                password=str(body.get("password", "")),
                display_name=str(body.get("display_name", "")),
                synthetic=bool(body.get("synthetic", True)),
            )
            session["account_id"] = account.id
            return jsonify({"account": _account_payload(account)}), 201

    @app.post("/api/v1/auth/login")
    def login() -> Any:
        body = json_body()
        with session_scope(factory) as session_db:
            account = authenticate(session_db, email=str(body.get("email", "")), password=str(body.get("password", "")))
            if account is None:
                return jsonify({"error": {"code": "invalid_credentials", "message": "Email or password is incorrect."}}), 401
            session["account_id"] = account.id
            return jsonify({"account": _account_payload(account)})

    @app.post("/api/v1/auth/logout")
    def logout() -> Any:
        session.clear()
        return jsonify({"status": "signed_out"})

    @app.get("/api/v1/me")
    def me() -> Any:
        with session_scope(factory) as session_db:
            account = current_account(session_db)
            if account is None:
                return jsonify({"account": None})
            return jsonify({"account": _account_payload(account)})

    @app.get("/api/v1/courses")
    def courses() -> Any:
        page = max(int(request.args.get("page", "1")), 1)
        page_size = min(max(int(request.args.get("page_size", "20")), 1), 100)
        query = (request.args.get("q") or "").strip()
        with session_scope(factory) as session_db:
            statement = select(Course).order_by(Course.stable_code.asc())
            if query:
                pattern = f"%{query}%"
                statement = statement.where((Course.stable_code.ilike(pattern)) | (Course.canonical_title.ilike(pattern)))
            total = session_db.scalar(select(func.count()).select_from(statement.subquery())) or 0
            rows = session_db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
            return jsonify({
                "items": [_course_payload(row, session_db) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            })

    @app.get("/api/v1/courses/<course_id>")
    def course_detail(course_id: str) -> Any:
        with session_scope(factory) as session_db:
            course = session_db.get(Course, course_id)
            if course is None:
                raise NotFoundError("Course not found.")
            return jsonify(_course_payload(course, session_db, detailed=True))

    @app.get("/api/v1/reviews")
    def reviews() -> Any:
        page = max(int(request.args.get("page", "1")), 1)
        page_size = min(max(int(request.args.get("page_size", "20")), 1), 100)
        with session_scope(factory) as session_db:
            statement = (
                select(Review, ReviewRevision)
                .join(ReviewRevision, (ReviewRevision.review_id == Review.id) & (ReviewRevision.revision == Review.published_revision))
                .where(Review.status.in_(["published", "submitted"]), Review.published_revision.is_not(None))
                .order_by(Review.created_at.desc(), Review.id.desc())
            )
            rows = session_db.execute(statement.offset((page - 1) * page_size).limit(page_size)).all()
            total = session_db.scalar(select(func.count()).select_from(Review).where(Review.status.in_(["published", "submitted"]), Review.published_revision.is_not(None))) or 0
            return jsonify({"items": [_review_payload(review, revision) for review, revision in rows], "page": page, "page_size": page_size, "total": total})

    @app.post("/api/v1/reviews")
    @require_account
    def create_review_endpoint() -> Any:
        body = json_body()
        data = _review_input(body)
        with session_scope(factory) as session_db:
            review = create_review(session_db, actor_id=g.account_id, data=data, idempotency_key=request.headers.get("Idempotency-Key"))
            revision = session_db.scalar(select(ReviewRevision).where(ReviewRevision.review_id == review.id, ReviewRevision.revision == review.current_revision))
            return jsonify(_review_payload(review, revision)), 201

    @app.post("/api/v1/reviews/<review_id>/submit")
    @require_account
    def submit_review_endpoint(review_id: str) -> Any:
        with session_scope(factory) as session_db:
            review = submit_review(session_db, actor_id=g.account_id, review_id=review_id)
            return jsonify({"review_id": review.id, "status": review.status, "revision": review.current_revision})

    @app.patch("/api/v1/reviews/<review_id>")
    @require_account
    def edit_review_endpoint(review_id: str) -> Any:
        body = json_body()
        expected = int(request.headers.get("If-Match-Revision", body.get("revision", "0")))
        with session_scope(factory) as session_db:
            review = edit_review(session_db, actor_id=g.account_id, review_id=review_id, data=_review_input(body), expected_revision=expected)
            revision = session_db.scalar(select(ReviewRevision).where(ReviewRevision.review_id == review.id, ReviewRevision.revision == review.current_revision))
            return jsonify(_review_payload(review, revision))

    @app.get("/api/v1/courses/<course_id>/statistics")
    def course_statistics_endpoint(course_id: str) -> Any:
        with session_scope(factory) as session_db:
            if session_db.get(Course, course_id) is None:
                raise NotFoundError("Course not found.")
            statistics = course_statistics(session_db, course_id=course_id, term_id=request.args.get("term_id"))
            return jsonify(_statistics_payload(statistics))

    @app.get("/api/v1/rankings")
    def rankings_endpoint() -> Any:
        preferences = RankingPreferences(
            workload_tolerance_hours=float(request.args.get("workload_tolerance_hours", "10")),
            evidence_weight=float(request.args.get("evidence_weight", ".25")),
            workload_weight=float(request.args.get("workload_weight", ".25")),
            degree_progress_weight=float(request.args.get("degree_progress_weight", ".25")),
            preference_weight=float(request.args.get("preference_weight", ".25")),
        )
        with session_scope(factory) as session_db:
            candidates: list[CourseCandidate] = []
            for course in session_db.scalars(select(Course).order_by(Course.stable_code)).all():
                statistics = course_statistics(session_db, course_id=course.id)
                candidates.append(CourseCandidate(course.id, course.stable_code, course.canonical_title, True, statistics.overall.mean, statistics.review_count, statistics.workload_mean_hours, 0.0, 0.0))
            return jsonify({"items": [_ranked_payload(item) for item in rank_courses(candidates, preferences)], "assumptions": {"academic_feasibility": "caller must validate prerequisites and availability before ranking", "preferences": preferences.__dict__ if hasattr(preferences, "__dict__") else {"workload_tolerance_hours": preferences.workload_tolerance_hours, "evidence_weight": preferences.evidence_weight, "workload_weight": preferences.workload_weight, "degree_progress_weight": preferences.degree_progress_weight, "preference_weight": preferences.preference_weight}}})

    @app.post("/api/v1/reviews/<review_id>/helpful")
    @require_account
    def helpful_vote_endpoint(review_id: str) -> Any:
        body = json_body()
        with session_scope(factory) as session_db:
            vote = vote_helpful(session_db, account_id=g.account_id, review_id=review_id, helpful=bool(body.get("helpful", True)))
            return jsonify({"review_id": vote.review_id, "helpful": vote.helpful})

    @app.post("/api/v1/reviews/<review_id>/report")
    @require_account
    def report_review_endpoint(review_id: str) -> Any:
        body = json_body()
        with session_scope(factory) as session_db:
            report = report_review(session_db, account_id=g.account_id, review_id=review_id, reason=str(body.get("reason", "")))
            return jsonify({"report_id": report.id, "review_id": report.review_id, "status": report.status}), 201

    @app.get("/api/v1/moderation/queue")
    @require_account
    def moderation_queue_endpoint() -> Any:
        with session_scope(factory) as session_db:
            account = session_db.get(Account, g.account_id)
            if account is None or "moderator" not in set(account.roles_json):
                raise PermissionDenied("The moderator role is required.")
            return jsonify({"items": [{"review_id": review.id, "revision": revision, "open_reports": reports} for review, revision, reports in moderation_queue(session_db)]})

    @app.post("/api/v1/moderation/reviews/<review_id>")
    @require_account
    def moderate_review_endpoint(review_id: str) -> Any:
        body = json_body()
        with session_scope(factory) as session_db:
            review = moderate_review(session_db, moderator_id=g.account_id, review_id=review_id, target=str(body.get("decision", "")), reason=str(body.get("reason", "")))
            return jsonify({"review_id": review.id, "status": review.status, "revision": review.current_revision})

    @app.get("/api/v1/reconciliation")
    @require_account
    def reconciliation() -> Any:
        with session_scope(factory) as session_db:
            account = session_db.get(Account, g.account_id)
            if account is None or "moderator" not in set(account.roles_json):
                raise PermissionDenied("The moderator role is required.")
            return jsonify(reconcile(session_db, repair=request.args.get("repair") == "1"))

    @app.get("/")
    def dashboard() -> Any:
        return render_template("dashboard.html")

    return app


def _statistics_payload(statistics: Any) -> dict[str, Any]:
    return {
        "review_count": statistics.review_count,
        "overall": {"count": statistics.overall.count, "mean": statistics.overall.mean, "lower": statistics.overall.lower, "upper": statistics.overall.upper, "warning": statistics.overall.warning},
        "difficulty": {"count": statistics.difficulty.count, "mean": statistics.difficulty.mean, "lower": statistics.difficulty.lower, "upper": statistics.difficulty.upper, "warning": statistics.difficulty.warning},
        "workload": {"mean_hours_per_week": statistics.workload_mean_hours, "quantiles_hours_per_week": statistics.workload_quantiles_hours},
        "recommend_rate": statistics.recommend_rate,
        "comparison_warning": statistics.comparison_warning,
    }


def _ranked_payload(ranked: Any) -> dict[str, Any]:
    return {"course": {"id": ranked.candidate.course_id, "code": ranked.candidate.code, "title": ranked.candidate.title}, "score": ranked.score, "factors": ranked.factors, "explanation": ranked.explanation, "review_count": ranked.candidate.review_count}


def _account_payload(account: Account) -> dict[str, Any]:
    return {"id": account.id, "email": account.email, "display_name": account.display_name, "roles": account.roles_json, "synthetic": account.synthetic}


def _course_payload(course: Course, session_db: Session, *, detailed: bool = False) -> dict[str, Any]:
    groups = session_db.execute(
        select(CourseAggregate).where(CourseAggregate.course_id == course.id).order_by(CourseAggregate.term_id)
    ).scalars().all()
    total = sum(row.review_count for row in groups)
    overall = sum(row.sum_overall for row in groups)
    difficulty = sum(row.sum_difficulty for row in groups)
    workload = sum(row.sum_workload for row in groups)
    payload: dict[str, Any] = {
        "id": course.id,
        "code": course.stable_code,
        "title": course.canonical_title,
        "evidence": {"published_review_count": total, "overall_mean": overall / total if total else None, "difficulty_mean": difficulty / total if total else None, "workload_mean_hours": workload / total if total else None, "missing": total == 0},
    }
    if detailed:
        payload["term_breakdown"] = [{"term_id": row.term_id, "review_count": row.review_count, "overall_mean": row.sum_overall / row.review_count if row.review_count else None} for row in groups]
    return payload


def _review_input(body: dict[str, Any]) -> ReviewInput:
    return ReviewInput(
        course_id=str(body.get("course_id", "")),
        term_id=str(body.get("term_id", "")),
        professor=str(body.get("professor", "")),
        difficulty=int(body.get("difficulty", 0)),
        workload_hours=int(body.get("workload_hours", -1)),
        overall=int(body.get("overall", 0)),
        would_recommend=bool(body.get("would_recommend", False)),
        comment=str(body.get("comment")) if body.get("comment") is not None else None,
    )


def _review_payload(review: Review, revision: ReviewRevision | None) -> dict[str, Any]:
    return {"id": review.id, "course_id": review.course_id, "term_id": review.term_id, "status": review.status, "revision": review.current_revision, "published_revision": review.published_revision, "content": None if revision is None else {"professor": revision.professor, "difficulty": revision.difficulty, "workload_hours": revision.workload_hours, "overall": revision.overall, "would_recommend": revision.would_recommend, "comment": revision.comment}}


def run() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5001")), debug=False)
