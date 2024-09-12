# Performance and query-plan report

Performance gates are separate from semantic correctness. The benchmark command records five repetitions of the current paginated course read on the declared local development machine and writes a JSON report. The report is not a production SLO and does not claim the PostgreSQL workload target.

The production target is p95 below 250 ms for paginated course/review reads at 50 concurrent clients and an honest representative eight-term planning response within 15 seconds. A solver timeout is `unknown` or `feasible with a bound`, never proven infeasibility or optimality. Query timeouts are configured at the PostgreSQL connection with `DATABASE_QUERY_TIMEOUT_MS`; SQLite uses its connection lock timeout.

The important query shapes are:

```sql
SELECT c.id, c.stable_code, c.canonical_title
FROM courses AS c
WHERE c.stable_code ILIKE :pattern OR c.canonical_title ILIKE :pattern
ORDER BY c.stable_code
LIMIT :page_size OFFSET :offset;

SELECT r.id, rr.overall, rr.difficulty, rr.workload_hours
FROM reviews AS r
JOIN review_revisions AS rr
  ON rr.review_id = r.id AND rr.revision = r.published_revision
WHERE r.status IN ('published', 'submitted')
  AND r.published_revision IS NOT NULL
ORDER BY r.created_at DESC, r.id DESC
LIMIT :page_size OFFSET :offset;
```

The schema has composite status/course/term, pending-task lease, and outbox claim indexes. PostgreSQL acceptance must preserve `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` output with raw repetitions and query counts. This repository's local SQLite benchmark is evidence of command reproducibility only; the PostgreSQL plan and concurrency numbers remain an unresolved gate until a PostgreSQL service is available.
