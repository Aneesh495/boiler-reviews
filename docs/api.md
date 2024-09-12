# HTTP API reference

All write endpoints accept JSON and return JSON errors of the shape `{ "error": { "code": "...", "message": "...", "fields": {} } }`. API writes require an authenticated session and CSRF protection in non-test environments. Clients should send `X-Request-ID` for trace correlation and `Idempotency-Key` for retryable creates. Review edits use `If-Match-Revision` or a body `revision` token.

## Identity

- `POST /api/v1/auth/register` creates a synthetic local account and signs it in. It does not verify enrollment or send mail.
- `POST /api/v1/auth/login` authenticates an Argon2 password hash.
- `POST /api/v1/auth/logout` clears the session.
- `GET /api/v1/me` reports the current account or `null`.
- `GET /api/v1/csrf` returns the CSRF token for browser clients.

## Catalog and evidence

- `GET /api/v1/courses?q=&page=&page_size=` returns stable course identities with bounded pagination.
- `GET /api/v1/courses/{course_id}` returns course evidence and term breakdown.
- `GET /api/v1/courses/{course_id}/statistics?term_id=` returns counts, shrinkage interval, workload mean/quantiles, recommendation rate, and small-sample warnings.
- `GET /api/v1/rankings` returns preference factor contributions. Feasibility is a separate planner/validator concern and an infeasible course is never assigned a preference score.
- `GET /api/v1/reviews?page=&page_size=` returns public approved revisions. A pending edit continues to expose the last approved revision.

## Review workflow

- `POST /api/v1/reviews` creates an owner-scoped draft.
- `POST /api/v1/reviews/{id}/submit` submits the current revision.
- `PATCH /api/v1/reviews/{id}` creates a new revision and enforces the optimistic token.
- `POST /api/v1/moderation/reviews/{id}` accepts `decision: published|hidden|rejected` and a reason. Only the moderator role may call it.
- `GET /api/v1/moderation/queue` returns submitted revisions and open report counts.
- `POST /api/v1/reviews/{id}/helpful` upserts a helpful vote; authors cannot vote on their own review.
- `POST /api/v1/reviews/{id}/report` creates an idempotent open moderation report.
- `GET /api/v1/reconciliation?repair=1` compares or repairs stored aggregates and records an audit event.

## Planning and scheduling

`POST /api/v1/plans/solve` accepts version identifiers, terms, fixed-point credit units, course prerequisite ASTs, requirements, completed evidence, pins, exclusions, objective, seed, and time limit. The response reports `optimal`, `feasible`, `infeasible`, `unknown`, or `invalid_model`, assignment, objective, best bound, diagnostics, and independent-validator output.

`POST /api/v1/plans/validate` accepts the same request plus `assignment` and independently recomputes academic validity. It does not call the optimizer.

`POST /api/v1/schedules/choose` accepts `planned_courses`, section options, and blocked meetings. It returns a selected section per course, conflicts, unknown meeting warnings, and capacity observation fields. `POST /api/v1/schedules/calendar` returns a timezone-aware `text/calendar` attachment with bounded weekly recurrence.

## Operations

- `GET /health` is a process health check.
- `GET /ready` verifies database readiness and returns 503 when unavailable.
- `GET /metrics` returns local counters/timing percentiles without student records.
- `python -m boiler_reviews.worker --once` processes one leased task.

A browser that disconnects should poll the durable task record or reconnect to a future task-status endpoint; it must not infer completion from a lost response.
