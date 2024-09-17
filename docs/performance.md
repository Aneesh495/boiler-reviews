# Performance and query-plan report

Performance gates are separate from semantic correctness. The benchmark command records five repetitions of the current paginated course read on the declared local development machine and writes a JSON report. The report is not a production SLO and does not claim the PostgreSQL workload target.

A measured PostgreSQL smoke campaign and the required full campaign completed with zero aggregate mismatches. The full report records one hundred concurrent workers, one hundred operations per worker, zero failures, and ten thousand committed operations in `evidence/postgres-full-attempt.json`.

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
WHERE r.status IN ('published', 'submitted', 'rejected')
  AND r.published_revision IS NOT NULL
ORDER BY r.created_at DESC, r.id DESC
LIMIT :page_size OFFSET :offset;
```

The schema has composite status/course/term, pending-task lease, and outbox claim indexes. PostgreSQL acceptance preserved migration, concurrency, and restore evidence; query-plan output remains a production-tuning artifact to collect on a 5,000-course/100,000-review dataset.
