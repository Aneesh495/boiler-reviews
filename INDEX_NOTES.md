# Index notes (Stage 3)

This file lists each index, what it is for, and where the app uses the matching query patterns.

SQLite may use an index for some queries and fall back to table scans depending on data size and the query planner; these indexes match the **filters and joins** this app actually runs.

---

## `idx_reviews_course_id` — `CREATE INDEX ... ON reviews(course_id)`

| | |
|--|--|
| **Supports** | Equality filter `r.course_id = ?` and the foreign-key join `JOIN courses c ON r.course_id = c.id`. |
| **Example SQL** | Report: `WHERE r.course_id = ?` (when a course filter is chosen). |
| **Benefit** | Quickly finds review rows for one course instead of scanning every review when the table grows. |
| **Where in the app** | `report()` in `app.py` (filtered report); `recalculate_course_stats()` uses `WHERE course_id = ?` when recomputing stats. |

---

## `idx_reviews_semester_id` — `ON reviews(semester_id)`

| | |
|--|--|
| **Supports** | Equality filter `r.semester_id = ?` and the join `JOIN semesters s ON r.semester_id = s.id`. |
| **Example SQL** | Report: `WHERE r.semester_id = ?`. |
| **Benefit** | Narrows reviews to one semester for filters and joins. |
| **Where in the app** | `report()` in `app.py`. |

---

## `idx_reviews_overall_rating` — `ON reviews(overall_rating)`

| | |
|--|--|
| **Supports** | Range/equality predicates on overall rating, especially `r.overall_rating >= ?`. |
| **Example SQL** | Report: “minimum overall rating” filter. |
| **Benefit** | Helps SQLite locate rows at or above a rating threshold. |
| **Where in the app** | `report()` in `app.py`. |

---

## `idx_reviews_would_recommend` — `ON reviews(would_recommend)`

| | |
|--|--|
| **Supports** | Equality filter `r.would_recommend = ?` (values `0` or `1`). |
| **Example SQL** | Report: recommend yes/no filter. |
| **Benefit** | Speeds up boolean-style filtering on a low-cardinality column when combined with other filters. |
| **Where in the app** | `report()` in `app.py`. |

---

## `idx_reviews_course_semester_overall` — `ON reviews(course_id, semester_id, overall_rating)`

| | |
|--|--|
| **Supports** | The common **combined** report filter: same course, same semester, and a minimum overall rating. |
| **Example SQL** | `WHERE r.course_id = ? AND r.semester_id = ? AND r.overall_rating >= ?` |
| **Benefit** | One composite index aligns with all three predicates used together (fewer row lookups than three separate single-column filters alone in some plans). |
| **Where in the app** | `report()` when multiple filters are applied at once. |

---

## `idx_semesters_term_year` — `ON semesters(term, year)`

| | |
|--|--|
| **Supports** | `ORDER BY year DESC, term ASC` and lookups on term/year pairs. |
| **Example SQL** | `SELECT ... FROM semesters ORDER BY year DESC, term ASC` (dropdown population). |
| **Benefit** | Makes ordered semester lists cheaper as more terms are added. |
| **Where in the app** | `fetch_dropdown_data()` in `app.py` (course/semester dropdowns on review form and report). |

---

## `courses(course_code)` — unique constraint (built-in index)

| | |
|--|--|
| **Supports** | Fast lookup by exact course code; SQLite automatically indexes `UNIQUE` columns. |
| **Benefit** | `ORDER BY course_code` and code-based joins stay efficient. |
| **Where in the app** | Review list ordering by `c.course_code`; seed script lookups by code. |

No separate `CREATE INDEX` was added for `course_code` because the unique constraint already creates an index.
