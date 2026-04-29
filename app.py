from __future__ import annotations

import os
import sqlite3
from typing import Any

from flask import Flask, flash, redirect, render_template, request, url_for

# -----------------------------------------------------------------------------
# Deployment-safe config (works locally and on Linux VM)
# -----------------------------------------------------------------------------
PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "course_reviews.db")
PORT = int(os.environ.get("PORT", "5001"))
SECRET_KEY = os.environ.get(
    "SECRET_KEY", os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")
)

# Flask app setup
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY


def get_db_connection() -> sqlite3.Connection:
    """
    Create a SQLite connection and return rows as dictionaries.

    We also enable foreign key enforcement (SQLite requires this per-connection).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def recalculate_course_stats(course_id: int, conn: sqlite3.Connection) -> None:
    """
    Recompute one row in `course_stats` from all `reviews` for that course.

    Stage 3 demo: this runs in the same transaction as INSERT/UPDATE/DELETE on
    `reviews`, so readers never see "new review row but stale averages" (or the
    reverse) from this app's own writes.
    """
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS review_count,
            COALESCE(AVG(overall_rating), 0) AS avg_overall,
            COALESCE(AVG(difficulty_rating), 0) AS avg_difficulty,
            COALESCE(AVG(workload_hours), 0) AS avg_workload,
            COALESCE(SUM(CASE WHEN would_recommend = 1 THEN 1 ELSE 0 END), 0) AS recommend_count
        FROM reviews
        WHERE course_id = ?;
        """,
        (course_id,),
    ).fetchone()
    assert row is not None
    conn.execute(
        """
        INSERT INTO course_stats (
            course_id,
            review_count,
            avg_overall,
            avg_difficulty,
            avg_workload,
            recommend_count
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(course_id) DO UPDATE SET
            review_count = excluded.review_count,
            avg_overall = excluded.avg_overall,
            avg_difficulty = excluded.avg_difficulty,
            avg_workload = excluded.avg_workload,
            recommend_count = excluded.recommend_count;
        """,
        (
            course_id,
            row["review_count"],
            row["avg_overall"],
            row["avg_difficulty"],
            row["avg_workload"],
            row["recommend_count"],
        ),
    )


def create_review_transaction(
    conn: sqlite3.Connection,
    course_id: int,
    semester_id: int,
    professor: str,
    difficulty_rating: int,
    workload_hours: int,
    overall_rating: int,
    would_recommend: int,
    comment: str | None,
) -> None:
    """
    Insert a review and refresh `course_stats` atomically.

    Stage 3 demo / WHY TRANSACTION:
      Without a transaction, if the process crashed after inserting into `reviews`
      but before updating `course_stats`, the stats page would lie until repaired.
      Wrapping both steps commits them together or rolls both back on error.

    ISOLATION (SQLite):
      SQLite uses SERIALIZABLE isolation by default for plain transactions: one
      writer at a time, and readers see a consistent database state.

    CONCURRENCY:
      This app is mostly single-user, but if two users edited the same course at
      once, serialized writes prevent interleaved partial updates to `reviews` vs
      `course_stats` from this code path.
    """
    # BEGIN IMMEDIATE reserves the write lock up front for teaching clarity
    # (both writers and this demo's narrative about "one atomic unit of work").
    conn.execute("BEGIN IMMEDIATE;")
    try:
        # Parameterized INSERT: user fields are always passed as parameters, never
        # concatenated into SQL strings — the main defense against SQL injection.
        conn.execute(
            """
            INSERT INTO reviews (
                course_id,
                semester_id,
                professor,
                difficulty_rating,
                workload_hours,
                overall_rating,
                would_recommend,
                comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                course_id,
                semester_id,
                professor,
                difficulty_rating,
                workload_hours,
                overall_rating,
                would_recommend,
                comment,
            ),
        )
        recalculate_course_stats(course_id, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def update_review_transaction(
    conn: sqlite3.Connection,
    review_id: int,
    course_id: int,
    semester_id: int,
    professor: str,
    difficulty_rating: int,
    workload_hours: int,
    overall_rating: int,
    would_recommend: int,
    comment: str | None,
) -> bool:
    """
    Update a review and refresh stats for every course touched (old and new).

    If the course_id changes, both courses need recomputation; doing that inside
    one transaction keeps both courses’ `course_stats` consistent with `reviews`.
    """
    conn.execute("BEGIN IMMEDIATE;")
    try:
        # Parameterized SELECT — review id comes from the URL but still uses `?`.
        prev = conn.execute(
            "SELECT course_id FROM reviews WHERE id = ?;",
            (review_id,),
        ).fetchone()
        if prev is None:
            conn.rollback()
            return False
        prev_course_id = prev["course_id"]

        conn.execute(
            """
            UPDATE reviews
            SET
                course_id = ?,
                semester_id = ?,
                professor = ?,
                difficulty_rating = ?,
                workload_hours = ?,
                overall_rating = ?,
                would_recommend = ?,
                comment = ?
            WHERE id = ?;
            """,
            (
                course_id,
                semester_id,
                professor,
                difficulty_rating,
                workload_hours,
                overall_rating,
                would_recommend,
                comment,
                review_id,
            ),
        )
        recalculate_course_stats(prev_course_id, conn)
        if prev_course_id != course_id:
            recalculate_course_stats(course_id, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True


def delete_review_transaction(conn: sqlite3.Connection, review_id: int) -> bool:
    """Delete a review and refresh that course’s stats in one transaction."""
    conn.execute("BEGIN IMMEDIATE;")
    try:
        prev = conn.execute(
            "SELECT course_id FROM reviews WHERE id = ?;",
            (review_id,),
        ).fetchone()
        if prev is None:
            conn.rollback()
            return False
        course_id = prev["course_id"]
        conn.execute("DELETE FROM reviews WHERE id = ?;", (review_id,))
        recalculate_course_stats(course_id, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True


def refresh_all_course_stats(conn: sqlite3.Connection) -> None:
    """Recompute stats for every course (used after bulk seeding)."""
    rows = conn.execute("SELECT id FROM courses;").fetchall()
    for row in rows:
        recalculate_course_stats(int(row["id"]), conn)


def fetch_dropdown_data() -> dict[str, list[sqlite3.Row]]:
    """
    Load dropdown options from the database (NOT hardcoded).

    This helps satisfy the assignment requirement that at least one UI dropdown
    is populated dynamically from database rows.

    Uses parameterized queries only where user input exists (report route);
    here there is no untrusted input in the SQL.
    """
    conn = get_db_connection()
    courses = conn.execute(
        "SELECT id, course_code, course_name FROM courses ORDER BY course_code;"
    ).fetchall()
    semesters = conn.execute(
        "SELECT id, term, year FROM semesters ORDER BY year DESC, term ASC;"
    ).fetchall()
    conn.close()
    return {"courses": courses, "semesters": semesters}


def parse_int(value: str | None) -> int | None:
    """
    Convert a form/query value to int if present; otherwise return None.

    Invalid numbers (e.g. "abc") return None so we can show a validation error
    instead of crashing — part of basic server-side validation (Stage 3).
    """
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def collect_review_errors(
    course_id: int | None,
    semester_id: int | None,
    professor: str,
    difficulty_rating: int | None,
    workload_hours: int | None,
    overall_rating: int | None,
    would_recommend: int | None,
    *,
    raw_course_id: str | None,
    raw_semester_id: str | None,
    raw_difficulty: str | None,
    raw_workload: str | None,
    raw_overall: str | None,
    raw_recommend: str | None,
) -> list[str]:
    """
    Server-side validation for review forms (Stage 3).

    - Trimming is applied before INSERT (professor/comment done in the route).
    - Numeric fields must be valid integers and in allowed ranges.
    """
    errors: list[str] = []

    def bad_int(raw: str | None, parsed: int | None, label: str) -> None:
        if raw is None:
            return
        s = raw.strip()
        if s == "":
            return
        if parsed is None:
            errors.append(f"{label} must be a valid whole number.")

    bad_int(raw_course_id, course_id, "Course")
    bad_int(raw_semester_id, semester_id, "Semester")
    bad_int(raw_difficulty, difficulty_rating, "Difficulty rating")
    bad_int(raw_workload, workload_hours, "Workload hours")
    bad_int(raw_overall, overall_rating, "Overall rating")
    bad_int(raw_recommend, would_recommend, "Would recommend")

    if course_id is None and (raw_course_id or "").strip() == "":
        errors.append("Course is required.")
    if semester_id is None and (raw_semester_id or "").strip() == "":
        errors.append("Semester is required.")
    if not professor:
        errors.append("Professor is required.")
    if difficulty_rating is None and (raw_difficulty or "").strip() == "":
        errors.append("Difficulty rating is required.")
    elif difficulty_rating is not None and not (1 <= difficulty_rating <= 5):
        errors.append("Difficulty rating must be between 1 and 5.")
    if workload_hours is None and (raw_workload or "").strip() == "":
        errors.append("Workload hours is required.")
    elif workload_hours is not None and workload_hours < 0:
        errors.append("Workload hours cannot be negative.")
    if overall_rating is None and (raw_overall or "").strip() == "":
        errors.append("Overall rating is required.")
    elif overall_rating is not None and not (1 <= overall_rating <= 5):
        errors.append("Overall rating must be between 1 and 5.")
    if would_recommend is None and (raw_recommend or "").strip() == "":
        errors.append("Would recommend is required.")
    elif would_recommend is not None and would_recommend not in (0, 1):
        errors.append("Would recommend must be yes (1) or no (0).")

    return errors


@app.route("/")
def home():
    """Home page with links to core features."""
    return render_template("home.html")


@app.route("/reviews")
def reviews_list():
    """
    List all reviews in a joined table so users see readable course/semester names.

    Every JOIN/WHERE value is fixed SQL; only structure is static — no user
    string concatenation into the query (SQL injection is not introduced here).
    """
    conn = get_db_connection()
    reviews = conn.execute(
        """
        SELECT
            r.id,
            c.course_code,
            c.course_name,
            s.term,
            s.year,
            r.professor,
            r.difficulty_rating,
            r.workload_hours,
            r.overall_rating,
            r.would_recommend,
            r.comment
        FROM reviews r
        JOIN courses c ON r.course_id = c.id
        JOIN semesters s ON r.semester_id = s.id
        ORDER BY s.year DESC, s.term ASC, c.course_code ASC, r.id DESC;
        """
    ).fetchall()
    conn.close()
    return render_template("reviews.html", reviews=reviews)


@app.route("/reviews/new", methods=["GET", "POST"])
def review_new():
    """
    Create a new review.

    Stage 3 — SQL injection:
      All writes use `?` placeholders with a separate parameter tuple/list.
      Even if a user typed quotes or SQL keywords into professor/comment,
      sqlite3 sends those as *data*, not as executable SQL.
    """
    dropdowns = fetch_dropdown_data()

    if request.method == "POST":
        raw = request.form
        course_id = parse_int(raw.get("course_id"))
        semester_id = parse_int(raw.get("semester_id"))
        professor = (raw.get("professor") or "").strip()
        difficulty_rating = parse_int(raw.get("difficulty_rating"))
        workload_hours = parse_int(raw.get("workload_hours"))
        overall_rating = parse_int(raw.get("overall_rating"))
        would_recommend = parse_int(raw.get("would_recommend"))
        comment_raw = raw.get("comment") or ""
        comment = comment_raw.strip() or None

        errors = collect_review_errors(
            course_id,
            semester_id,
            professor,
            difficulty_rating,
            workload_hours,
            overall_rating,
            would_recommend,
            raw_course_id=raw.get("course_id"),
            raw_semester_id=raw.get("semester_id"),
            raw_difficulty=raw.get("difficulty_rating"),
            raw_workload=raw.get("workload_hours"),
            raw_overall=raw.get("overall_rating"),
            raw_recommend=raw.get("would_recommend"),
        )

        if errors:
            for e in errors:
                flash(e, "danger")
            form_data: dict[str, Any] = dict(request.form)
            return render_template(
                "review_form.html",
                mode="new",
                action_url=url_for("review_new"),
                form_data=form_data,
                courses=dropdowns["courses"],
                semesters=dropdowns["semesters"],
            )

        conn = get_db_connection()
        try:
            create_review_transaction(
                conn,
                int(course_id),
                int(semester_id),
                professor,
                int(difficulty_rating),
                int(workload_hours),
                int(overall_rating),
                int(would_recommend),
                comment,
            )
        except Exception:
            conn.close()
            flash("Could not save the review. Please try again.", "danger")
            form_data = dict(request.form)
            return render_template(
                "review_form.html",
                mode="new",
                action_url=url_for("review_new"),
                form_data=form_data,
                courses=dropdowns["courses"],
                semesters=dropdowns["semesters"],
            )
        conn.close()

        flash("Review created successfully.", "success")
        return redirect(url_for("reviews_list"))

    return render_template(
        "review_form.html",
        mode="new",
        action_url=url_for("review_new"),
        form_data={},
        courses=dropdowns["courses"],
        semesters=dropdowns["semesters"],
    )


@app.route("/reviews/<int:review_id>/edit", methods=["GET", "POST"])
def review_edit(review_id: int):
    """Edit an existing review (writes go through a transaction + stats refresh)."""
    dropdowns = fetch_dropdown_data()
    conn = get_db_connection()

    review = conn.execute("SELECT * FROM reviews WHERE id = ?;", (review_id,)).fetchone()
    if review is None:
        conn.close()
        flash("Review not found.", "warning")
        return redirect(url_for("reviews_list"))

    if request.method == "POST":
        raw = request.form
        course_id = parse_int(raw.get("course_id"))
        semester_id = parse_int(raw.get("semester_id"))
        professor = (raw.get("professor") or "").strip()
        difficulty_rating = parse_int(raw.get("difficulty_rating"))
        workload_hours = parse_int(raw.get("workload_hours"))
        overall_rating = parse_int(raw.get("overall_rating"))
        would_recommend = parse_int(raw.get("would_recommend"))
        comment_raw = raw.get("comment") or ""
        comment = comment_raw.strip() or None

        errors = collect_review_errors(
            course_id,
            semester_id,
            professor,
            difficulty_rating,
            workload_hours,
            overall_rating,
            would_recommend,
            raw_course_id=raw.get("course_id"),
            raw_semester_id=raw.get("semester_id"),
            raw_difficulty=raw.get("difficulty_rating"),
            raw_workload=raw.get("workload_hours"),
            raw_overall=raw.get("overall_rating"),
            raw_recommend=raw.get("would_recommend"),
        )

        if errors:
            conn.close()
            for e in errors:
                flash(e, "danger")
            form_data: dict[str, Any] = dict(request.form)
            return render_template(
                "review_form.html",
                mode="edit",
                action_url=url_for("review_edit", review_id=review_id),
                form_data=form_data,
                courses=dropdowns["courses"],
                semesters=dropdowns["semesters"],
            )

        try:
            ok = update_review_transaction(
                conn,
                review_id,
                int(course_id),
                int(semester_id),
                professor,
                int(difficulty_rating),
                int(workload_hours),
                int(overall_rating),
                int(would_recommend),
                comment,
            )
        except Exception:
            conn.close()
            flash("Could not update the review. Please try again.", "danger")
            form_data = dict(request.form)
            return render_template(
                "review_form.html",
                mode="edit",
                action_url=url_for("review_edit", review_id=review_id),
                form_data=form_data,
                courses=dropdowns["courses"],
                semesters=dropdowns["semesters"],
            )

        conn.close()
        if not ok:
            flash("Review not found.", "warning")
            return redirect(url_for("reviews_list"))

        flash("Review updated successfully.", "success")
        return redirect(url_for("reviews_list"))

    conn.close()
    form_data = {
        "course_id": str(review["course_id"]),
        "semester_id": str(review["semester_id"]),
        "professor": review["professor"],
        "difficulty_rating": str(review["difficulty_rating"]),
        "workload_hours": str(review["workload_hours"]),
        "overall_rating": str(review["overall_rating"]),
        "would_recommend": str(review["would_recommend"]),
        "comment": review["comment"] or "",
    }
    return render_template(
        "review_form.html",
        mode="edit",
        action_url=url_for("review_edit", review_id=review_id),
        form_data=form_data,
        courses=dropdowns["courses"],
        semesters=dropdowns["semesters"],
    )


@app.route("/reviews/<int:review_id>/delete", methods=["POST"])
def review_delete(review_id: int):
    """Delete a review (POST only to avoid accidental deletes via links)."""
    conn = get_db_connection()
    try:
        ok = delete_review_transaction(conn, review_id)
    except Exception:
        conn.close()
        flash("Could not delete the review. Please try again.", "danger")
        return redirect(url_for("reviews_list"))
    conn.close()
    if ok:
        flash("Review deleted successfully.", "success")
    else:
        flash("Review not found.", "warning")
    return redirect(url_for("reviews_list"))


@app.route("/course-stats")
def course_stats():
    """Stage 3: show precomputed per-course aggregates from `course_stats`."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.course_code,
            c.course_name,
            COALESCE(cs.review_count, 0) AS review_count,
            COALESCE(cs.avg_overall, 0) AS avg_overall,
            COALESCE(cs.avg_difficulty, 0) AS avg_difficulty,
            COALESCE(cs.avg_workload, 0) AS avg_workload,
            COALESCE(cs.recommend_count, 0) AS recommend_count
        FROM courses c
        LEFT JOIN course_stats cs ON cs.course_id = c.id
        ORDER BY c.course_code ASC;
        """
    ).fetchall()
    conn.close()
    return render_template("course_stats.html", rows=rows)


@app.route("/report", methods=["GET"])
def report():
    """
    Report page with optional filters + computed statistics.

    Stage 3 — SQL injection:
      The WHERE clause *template* is built from fixed strings like `r.course_id = ?`.
      Only bind parameters (`params`) carry user-chosen values — never f-strings
      that splice raw user text into SQL. That pattern keeps filtering safe.
    """
    dropdowns = fetch_dropdown_data()

    course_id = parse_int(request.args.get("course_id"))
    semester_id = parse_int(request.args.get("semester_id"))
    min_overall = parse_int(request.args.get("min_overall"))
    would_recommend = request.args.get("would_recommend")

    where_clauses: list[str] = []
    params: list[Any] = []

    if course_id is not None:
        where_clauses.append("r.course_id = ?")
        params.append(course_id)
    if semester_id is not None:
        where_clauses.append("r.semester_id = ?")
        params.append(semester_id)
    if min_overall is not None:
        where_clauses.append("r.overall_rating >= ?")
        params.append(min_overall)
    if would_recommend in ("0", "1"):
        where_clauses.append("r.would_recommend = ?")
        params.append(int(would_recommend))

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    conn = get_db_connection()
    rows = conn.execute(
        f"""
        SELECT
            r.id,
            c.course_code,
            c.course_name,
            s.term,
            s.year,
            r.professor,
            r.difficulty_rating,
            r.workload_hours,
            r.overall_rating,
            r.would_recommend,
            r.comment
        FROM reviews r
        JOIN courses c ON r.course_id = c.id
        JOIN semesters s ON r.semester_id = s.id
        {where_sql}
        ORDER BY s.year DESC, s.term ASC, c.course_code ASC, r.id DESC;
        """,
        params,
    ).fetchall()
    conn.close()

    total = len(rows)
    avg_overall = None
    avg_difficulty = None
    avg_workload = None
    recommend_pct = None

    if total > 0:
        avg_overall = sum(r["overall_rating"] for r in rows) / total
        avg_difficulty = sum(r["difficulty_rating"] for r in rows) / total
        avg_workload = sum(r["workload_hours"] for r in rows) / total
        recommend_count = sum(1 for r in rows if r["would_recommend"] == 1)
        recommend_pct = (recommend_count / total) * 100.0

    filters = {
        "course_id": "" if course_id is None else str(course_id),
        "semester_id": "" if semester_id is None else str(semester_id),
        "min_overall": "" if min_overall is None else str(min_overall),
        "would_recommend": "" if would_recommend is None else would_recommend,
    }

    return render_template(
        "report.html",
        courses=dropdowns["courses"],
        semesters=dropdowns["semesters"],
        filters=filters,
        rows=rows,
        total=total,
        avg_overall=avg_overall,
        avg_difficulty=avg_difficulty,
        avg_workload=avg_workload,
        recommend_pct=recommend_pct,
        where_clauses=where_clauses,
        params=params,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=PORT)
