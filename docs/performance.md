# Performance and query-plan report

Performance gates are separate from semantic correctness. The benchmark command records five repetitions of the current paginated course read on the declared local development machine and writes a JSON report. The report is not a production SLO and does not claim the PostgreSQL workload target.

A measured disposable PostgreSQL smoke campaign with ten workers and one hundred operations per worker completed with zero aggregate mismatches; its raw summary is `evidence/postgres-concurrency.json`. The required one-hundred-worker, ten-thousand-operation attempt is preserved as a failed raw record in `evidence/postgres-full-attempt.json`, so it is not silently substituted by the smaller run.

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
