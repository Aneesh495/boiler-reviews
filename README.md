# BoilerCourse Reviews (Stage 2 + Stage 3)

BoilerCourse Reviews is a beginner-friendly Flask + SQLite web app where users can create, edit, delete, and view course reviews, generate filtered reports with computed statistics, and view per-course aggregates stored in `course_stats`.

## Tech Stack

- Flask (Python)
- SQLite (via Python `sqlite3`, parameterized queries only)
- Jinja templates + HTML
- Bootstrap (CDN)

## Setup

### 1) Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2) Install requirements

```bash
pip install -r requirements.txt
```

### 3) Initialize the database

This creates `course_reviews.db` using `schema.sql` (includes Stage 3 tables and indexes).

```bash
python3 init_db.py
```

### 4) Seed sample data

`seed_db.py` imports `app.py`, so run it with the same Python environment where Flask is installed:

```bash
python3 seed_db.py
# or, if you use the project venv:
venv/bin/python seed_db.py
```

### 5) Run the app

```bash
python3 app.py
# or: venv/bin/python app.py
```

Then open `http://127.0.0.1:5001/`.

## SQL injection protection (Stage 3)

**What SQL injection is:** An attack where user-controlled text is interpreted as SQL code (for example, carefully chosen quotes and commands that change what the database executes).

**How this app defends:** Every query that touches user- or request-driven values uses SQLite’s `?` placeholders and passes values in a separate tuple/list. Untrusted text becomes *data bound to the query*, not part of the SQL string the engine parses.

**Where this applies:**

| Area | Route / behavior | Notes |
|------|------------------|--------|
| Review form | `POST /reviews/new`, `POST /reviews/<id>/edit` | `INSERT` / `UPDATE` use `?` for all columns. |
| Delete | `POST /reviews/<id>/delete` | `DELETE ... WHERE id = ?` |
| List / stats | `GET /reviews`, `GET /course-stats` | Static SQL (no user text concatenated). |
| Report filters | `GET /report` | `WHERE` uses fixed fragments like `r.course_id = ?`; only *parameters* hold filter values. |

Additional **server-side validation** trims professor/comment text, rejects non-numeric input where integers are required, and enforces rating ranges (see `collect_review_errors` in `app.py`).

More demo wording: `STAGE3_NOTES.md`. Index and transaction narratives: `INDEX_NOTES.md`, `TRANSACTIONS_NOTES.md`. AI: `AI_USAGE.md`.

## Assignment Requirements Summary

### Requirement 1 (Insert/Update/Delete UI)

- The **main table** is `reviews`.
- **Insert**: `/reviews/new`
- **Update**: `/reviews/<id>/edit`
- **Delete**: `/reviews/<id>/delete` (POST only)
- **List**: `/reviews` (shows joined course + semester info)

### Requirement 2 (Report + filters + statistics)

- Route: `/report`
- Optional filters:
  - Course (dropdown from DB)
  - Semester (dropdown from DB)
  - Minimum overall rating
  - Would recommend (Any / Yes / No)
- Results:
  - Matching rows table
  - Total count
  - Average overall rating
  - Average difficulty rating
  - Average workload hours
  - Recommendation percentage

### Stage 3: Course statistics + transactions

- Route: `/course-stats`
- Table: `course_stats` (precomputed per-course aggregates)
- Review writes use explicit transactions that refresh `course_stats` in the same unit of work as the `reviews` change.

### Dynamic DB-built UI

- The **course** and **semester** dropdowns are populated by querying `courses` and `semesters` tables in `app.py` (not hardcoded).

## Database Design

- **courses**
  - **PK**: `id`
  - **Unique**: `course_code` (SQLite indexes this automatically)
- **semesters**
  - **PK**: `id`
  - **Unique**: (`term`, `year`)
- **reviews**
  - **PK**: `id`
  - **FK**: `course_id → courses(id)`
  - **FK**: `semester_id → semesters(id)`
- **course_stats** (Stage 3)
  - **PK / FK**: `course_id → courses(id)`
  - Denormalized aggregates: counts and averages maintained when reviews change
