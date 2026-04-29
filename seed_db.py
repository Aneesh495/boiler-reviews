from app import DB_PATH, get_db_connection, refresh_all_course_stats


def main() -> None:
    """
    Seed the database with sample data for demos.

    Run after initializing:
      python3 seed_db.py

    Stage 3: after loading reviews, recomputes `course_stats` for every course
    so the Course Statistics page matches the seeded reviews.
    """
    conn = get_db_connection()
    try:
        # One transaction for seed inserts + stats refresh (demo-friendly).
        conn.execute("BEGIN;")

        courses = [
            ("CS348", "Information Systems"),
            ("ECE270", "Digital System Design"),
            ("MA261", "Multivariate Calculus"),
            ("CS251", "Data Structures and Algorithms"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO courses (course_code, course_name) VALUES (?, ?);",
            courses,
        )

        semesters = [
            ("Fall", 2025),
            ("Spring", 2026),
            ("Summer", 2026),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO semesters (term, year) VALUES (?, ?);",
            semesters,
        )

        course_rows = conn.execute("SELECT id, course_code FROM courses;").fetchall()
        course_id_by_code = {r["course_code"]: r["id"] for r in course_rows}

        semester_rows = conn.execute("SELECT id, term, year FROM semesters;").fetchall()
        semester_id_by_key = {(r["term"], r["year"]): r["id"] for r in semester_rows}

        reviews = [
            (
                course_id_by_code["CS348"],
                semester_id_by_key[("Fall", 2025)],
                "Dr. Smith",
                3,
                6,
                4,
                1,
                "Great intro to databases; projects were fair.",
            ),
            (
                course_id_by_code["CS348"],
                semester_id_by_key[("Spring", 2026)],
                "Prof. Nguyen",
                4,
                8,
                5,
                1,
                "Challenging exams but learned a lot from SQL.",
            ),
            (
                course_id_by_code["CS348"],
                semester_id_by_key[("Summer", 2026)],
                "Dr. Patel",
                2,
                5,
                4,
                1,
                "Summer pace — stay on top of weekly SQL exercises.",
            ),
            (
                course_id_by_code["ECE270"],
                semester_id_by_key[("Fall", 2025)],
                "Dr. Patel",
                4,
                10,
                4,
                1,
                "Labs take time, but you gain real hardware confidence.",
            ),
            (
                course_id_by_code["ECE270"],
                semester_id_by_key[("Spring", 2026)],
                "Prof. Lee",
                5,
                12,
                3,
                0,
                "Very fast pace; start labs early.",
            ),
            (
                course_id_by_code["ECE270"],
                semester_id_by_key[("Spring", 2026)],
                "Prof. Ortiz",
                3,
                7,
                4,
                1,
                "Clear rubric; grading felt consistent.",
            ),
            (
                course_id_by_code["MA261"],
                semester_id_by_key[("Fall", 2025)],
                "Dr. Johnson",
                5,
                9,
                3,
                0,
                "Conceptually tough, but recitation helped.",
            ),
            (
                course_id_by_code["MA261"],
                semester_id_by_key[("Summer", 2026)],
                "Prof. Chen",
                4,
                7,
                4,
                1,
                "Summer format is intense but manageable with practice.",
            ),
            (
                course_id_by_code["MA261"],
                semester_id_by_key[("Spring", 2026)],
                "Dr. Murphy",
                4,
                8,
                2,
                0,
                "Exams were rough — drill past papers.",
            ),
            (
                course_id_by_code["CS251"],
                semester_id_by_key[("Spring", 2026)],
                "Dr. Alvarez",
                4,
                11,
                4,
                1,
                "Projects are time-consuming but great for interview prep.",
            ),
            (
                course_id_by_code["CS251"],
                semester_id_by_key[("Fall", 2025)],
                "Prof. Kim",
                3,
                8,
                5,
                1,
                "Clear lectures and helpful office hours.",
            ),
            (
                course_id_by_code["CS251"],
                semester_id_by_key[("Fall", 2025)],
                "Dr. Brooks",
                4,
                9,
                3,
                0,
                "Interesting material; homework load spikes before midterms.",
            ),
        ]

        existing_count = conn.execute("SELECT COUNT(*) AS c FROM reviews;").fetchone()["c"]
        if existing_count == 0:
            conn.executemany(
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
                reviews,
            )

        # Keep precomputed aggregates aligned with `reviews` (Stage 3).
        refresh_all_course_stats(conn)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"Seeded database at {DB_PATH} (reviews + course_stats).")


if __name__ == "__main__":
    main()
