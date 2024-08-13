# Boiler Reviews

Flask + SQLite course review app: CRUD on reviews, filtered reports with aggregate statistics, and precomputed per-course metrics in `course_stats` maintained inside the same transaction as writes.

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

## SQL injection protection

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

Implementation notes: `INDEX_NOTES.md`, `TRANSACTIONS_NOTES.md`.

## Routes

| Route | Behavior |
| --- | --- |
| `/reviews`, `/reviews/new`, `/reviews/<id>/edit`, `/reviews/<id>/delete` | Review CRUD |
| `/report` | Filtered report (course, semester, rating, recommend) with aggregates |
| `/course-stats` | Precomputed per-course aggregates from `course_stats` |

Course and semester dropdowns are loaded from the database in `app.py`, not hardcoded.

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
- **course_stats**
  - **PK / FK**: `course_id → courses(id)`
  - Denormalized aggregates: counts and averages maintained when reviews change
