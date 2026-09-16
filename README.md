# Boiler Reviews

Flask + SQLite course review system with **parameterized SQL only**, filtered reporting, and **transactional maintenance** of denormalized `course_stats` on every review write.

## Features

| Area | Implementation |
| --- | --- |
| CRUD | `/reviews/new`, edit, delete (POST), list with course/semester joins |
| Reports | `/report` with course, semester, rating, recommend filters + aggregates |
| Aggregates | `/course-stats` reads precomputed `course_stats` |
| UI data | Course and semester dropdowns queried from DB in `app.py` (not hardcoded) |

## Data model

```mermaid
erDiagram
  courses ||--o{ reviews : has
  semesters ||--o{ reviews : has
  courses ||--|| course_stats : aggregates

  courses {
    int id PK
    string course_code UK
    string course_name
  }
  reviews {
    int id PK
    int course_id FK
    int semester_id FK
    int ratings...
  }
  course_stats {
    int course_id PK FK
    int review_count
    float avg_overall...
  }
```

Review mutations run inside explicit transactions; `course_stats` is refreshed in the **same unit of work** as the insert/update/delete (see `TRANSACTIONS_NOTES.md`).

## SQL injection posture

All user-controlled values bind via SQLite `?` placeholders. Dynamic report filters use fixed SQL fragments (`course_id = ?`, etc.); parameters never concatenate into query strings. Server-side validation in `collect_review_errors` enforces numeric ranges and trimmed text.

Route-level matrix documented in README history; deep dive: `INDEX_NOTES.md`.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 init_db.py      # schema.sql + indexes
python3 seed_db.py
python3 app.py
```

Open `http://127.0.0.1:5001/`.

## Stack

Flask, stdlib `sqlite3`, Jinja2, Bootstrap (CDN). No ORM; SQL is visible and reviewed.

## License

MIT
