import os
import sqlite3


DB_PATH = os.path.join(os.path.dirname(__file__), "course_reviews.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def main() -> None:
    """
    Initialize the SQLite database using schema.sql (Stage 2 + Stage 3).

    Creates `reviews`, `courses`, `semesters`, `course_stats`, and the Stage 3
    indexes. Run `python3 seed_db.py` afterward to load sample rows.

    Run:
      python3 init_db.py
    """
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Initialized database at: {DB_PATH}")


if __name__ == "__main__":
    main()
