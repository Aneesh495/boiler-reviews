-- BoilerCourse Reviews schema (Stage 2 + Stage 3)
-- NOTE: SQLite enforces foreign keys only when PRAGMA foreign_keys = ON.

-- Drop child tables first (foreign key order).
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS course_stats;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS semesters;

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    course_name TEXT NOT NULL
);

-- UNIQUE(course_code) creates an internal index in SQLite (good for lookups by code).
-- No extra index on course_code is required for this demo.

CREATE TABLE semesters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    year INTEGER NOT NULL,
    UNIQUE(term, year)
);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    semester_id INTEGER NOT NULL,
    professor TEXT NOT NULL,
    difficulty_rating INTEGER NOT NULL CHECK(difficulty_rating BETWEEN 1 AND 5),
    workload_hours INTEGER NOT NULL CHECK(workload_hours >= 0),
    overall_rating INTEGER NOT NULL CHECK(overall_rating BETWEEN 1 AND 5),
    would_recommend INTEGER NOT NULL CHECK(would_recommend IN (0,1)),
    comment TEXT,
    FOREIGN KEY(course_id) REFERENCES courses(id),
    FOREIGN KEY(semester_id) REFERENCES semesters(id)
);

-- Stage 3: precomputed per-course aggregates, kept in sync with reviews via transactions.
CREATE TABLE course_stats (
    course_id INTEGER PRIMARY KEY,
    review_count INTEGER NOT NULL DEFAULT 0,
    avg_overall REAL NOT NULL DEFAULT 0,
    avg_difficulty REAL NOT NULL DEFAULT 0,
    avg_workload REAL NOT NULL DEFAULT 0,
    recommend_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(course_id) REFERENCES courses(id)
);

-- ---------------------------------------------------------------------------
-- Indexes (Stage 3): each index supports frequent filters/joins/sorts.
-- See INDEX_NOTES.md for which route/query uses which index.
-- ---------------------------------------------------------------------------

-- Speeds: report filter `r.course_id = ?`, JOIN reviews→courses, stats recalc per course.
CREATE INDEX idx_reviews_course_id ON reviews(course_id);

-- Speeds: report filter `r.semester_id = ?`, JOIN reviews→semesters.
CREATE INDEX idx_reviews_semester_id ON reviews(semester_id);

-- Speeds: report filter `r.overall_rating >= ?`.
CREATE INDEX idx_reviews_overall_rating ON reviews(overall_rating);

-- Speeds: report filter `r.would_recommend = ?`.
CREATE INDEX idx_reviews_would_recommend ON reviews(would_recommend);

-- Speeds: common combined report filter (course + semester + min overall together).
CREATE INDEX idx_reviews_course_semester_overall ON reviews(course_id, semester_id, overall_rating);

-- Speeds: dropdown query `ORDER BY year DESC, term ASC` and semester-driven filters.
CREATE INDEX idx_semesters_term_year ON semesters(term, year);
