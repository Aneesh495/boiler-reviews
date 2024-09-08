# Operations and recovery

## Commands

`make bootstrap` creates the ignored local environment, installs the pinned package, creates the local instance directory, and applies ordered migrations. `make demo` activates the authored synthetic catalog fixture. `make migrate-legacy-dry-run` reads the backed-up legacy SQLite file without writing the new database and emits `evidence/migration-report.json`. `make census`, `make benchmark`, `make acceptance`, and `make verify` produce or check the reproducible evidence described in `docs/BUILD_STATUS.md`.

The production entry point is `gunicorn --bind 0.0.0.0:8000 app:app` with `APP_ENV=production`, an out-of-band `SECRET_KEY`, and PostgreSQL `DATABASE_URL`. The application never enables Flask debug mode in its direct entry point. Logs are JSON with request/task IDs and redact fields whose names imply credentials, tokens, cookies, authorization, or email. Metrics are intentionally basic in this release and are separate from semantic acceptance gates.

## Worker and restart behavior

The durable worker claims one task with a lease, increments a persisted fencing token, and processes it at least once. A stale worker cannot finish a task because writes require its owner and fencing token. `python -m boiler_reviews.worker --once` reconciles expired running leases, claims one task, and reports its count. A cancelled task is not restarted. The outbox uses the same lease pattern; handlers must be idempotent because a crash after the side effect and before `processed_at` causes a retry.

## Backup and restore

Back up PostgreSQL with `pg_dump --format=custom --file=boiler-reviews.dump "$DATABASE_URL"`; never commit the dump. Restore into an isolated database with `createdb boiler_reviews_restore` and `pg_restore --clean --if-exists --dbname="$RESTORE_DATABASE_URL" boiler-reviews.dump`, then run `make verify DATABASE_URL="$RESTORE_DATABASE_URL"`. A saved plan stores catalog and degree-rule version identifiers plus its assumptions. Re-running the independent validator against the restored plan input must produce the same status and violations. This is a reproducibility check, not a reservation or institutional identity guarantee.

## Recovery gates

If a catalog activation task is interrupted before commit, its staged snapshot remains staged and the active pointer is unchanged. If it is interrupted after commit, the idempotency key returns the existing activated snapshot. If review publication is interrupted, the review state, aggregate delta, audit record, and outbox event either all commit or all roll back. If solver publication is interrupted, the plan task result remains absent until the fenced owner finishes or the lease expires and another worker retries. Unknown institutional rules and missing meeting times remain visible rather than being inferred during recovery.
