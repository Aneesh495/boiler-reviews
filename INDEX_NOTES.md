# Query index notes

The active application uses SQLAlchemy models and ordered migrations. These notes describe the indexed access paths in the current schema; query plans remain database- and data-size-dependent.

| Index | Access path |
|---|---|
| `ix_course_versions_snapshot_code` | Snapshot-scoped course-version lookup by catalog code. |
| `ix_reviews_status_course_term` | Public/moderation review filtering by workflow state, course, and term. |
| `ix_tasks_status_lease` | Durable worker claims over queued/running tasks and expired leases. |
| `ix_outbox_pending` | Pending transactional outbox claims by processed state and lease expiry. |
| `uq_course_stable_code` | Stable course identity within an institution. |
| `uq_catalog_institution_version` | Immutable catalog version identity. |
| `uq_aggregate_course_term` | One sufficient-statistics row per course and term. |

The legacy `idx_semesters_term_year` index is not carried into the new schema. An index on `(term, year)` does not directly satisfy `ORDER BY year DESC, term ASC`; the old note made that claim incorrectly. PostgreSQL performance evidence must use `EXPLAIN (ANALYZE, BUFFERS)` against the actual production-shaped dataset.
