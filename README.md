# Boiler Reviews

Boiler Reviews is a course intelligence and academic planning system for inspecting review evidence, prerequisite rules, degree requirements, and feasible multi-term schedules. It is a modular monolith with a durable worker. The domain code is intentionally usable without Flask: prerequisite parsing, graph analysis, degree allocation, planning, independent validation, section scheduling, calendar export, review aggregates, and task leasing live under `src/boiler_reviews`.

> Demo identities, review rows, and catalog entries are synthetic. The system does not claim enrollment verification, university endorsement, or a reservation of section capacity.

## Five-minute local setup

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
make bootstrap
make demo
make dev
```

Open `http://127.0.0.1:5001/`. The default local database is ignored at `instance/boiler_reviews.sqlite3`. Production requires an explicit `SECRET_KEY` and PostgreSQL `DATABASE_URL`; the application does not enable Flask debug mode in its direct entry point.

The nested `client/` repository contains the React planner island. Its unit checks and production bundle are run with:

```bash
cd client
npm test -- --watchAll=false
npm run build
```

The first command exercises the accessible planner interactions. Dragging a course and moving the focused course with the left/right arrow keys use the same local state transition. Server validation is a separate action and returns actual violations.

## Product surfaces

- Course search and bounded pagination with explicit missing-evidence states.
- Course evidence by term, rating uncertainty, workload quantiles, recommendation rate, and small-sample warnings.
- Authenticated review drafts, optimistic revision edits, ownership checks, moderation decisions, reports, helpful votes, and audit events.
- Immutable catalog snapshots with stable course identities and atomic active-pointer changes.
- A prerequisite language for AND, OR, grade thresholds, credits, permission/placement predicates, and co-requisites.
- Versioned requirement allocation and deterministic degree audit.
- Multi-term planning with fixed-point credits, strict prerequisite ordering, co-requisite timing, availability, exclusions, pins, objectives, exact solver statuses, independent validation, and bounded exhaustive oracle checks.
- Section selection with real weekly meeting intervals, linked-section metadata, unknown-time warnings, and timezone-aware ICS export.
- Durable outbox and task leases with fencing, cancellation, restart reconciliation, and redacted operational logs.

## Architecture and contracts

- [System and data architecture](docs/architecture.md) contains the deployment topology, entity model, catalog activation, prerequisite compilation, review publication, task lifecycle, degree allocation, and failure recovery diagrams.
- [Catalog snapshot and prerequisite contract](docs/catalog-schema.md) defines the canonical document and grammar.
- [Review publication and aggregate invariants](docs/review-publication.md) explains revision visibility, sufficient statistics, shrinkage, and reconciliation.
- [Degree audit and planner model](docs/planner-model.md) defines allocation, fixed-point credits, solver statuses, objectives, and diagnostic limits.
- [Section scheduling and calendar contract](docs/section-scheduling.md) defines meeting semantics and recurrence boundaries.
- [HTTP API reference](docs/api.md) documents typed requests, errors, ownership, pagination, idempotency, CSRF, planner results, and operational endpoints.
- [Operations and recovery](docs/operations.md) documents migration, worker, backup/restore, fencing, and failure behavior.
- [Performance report](docs/performance.md) separates semantic checks from local timing and PostgreSQL query-plan gates.
- [Build status](docs/BUILD_STATUS.md) is the source-backed continuation record.

## Commands

| Command | Purpose |
|---|---|
| `make bootstrap` | Install the editable package, create local directories, and apply ordered migrations |
| `make demo` | Activate the authored synthetic catalog and create a local synthetic moderator |
| `make test` | Run the Python suite once |
| `make test-solver` | Run planner and oracle tests |
| `make migrate-legacy-dry-run` | Validate the preserved legacy SQLite backup without writing the active database |
| `make worker` | Reconcile expired leases and process one durable task |
| `make reconcile REPAIR=1` | Compare or explicitly repair published aggregate projections |
| `make benchmark` | Record five local query repetitions |
| `make acceptance` | Run the reproducible local acceptance profile and write evidence |
| `make verify` | Validate required evidence and fail when external gates remain unresolved |

`make acceptance` writes `evidence/ACCEPTANCE.json`, `evidence/migration-report.json`, and `evidence/benchmark.json`. The private source census is written to ignored `.runtime/source-census.json`. The local profile records the passing parser, catalog, recovery, Python, client, and bounded oracle checks. It also records unresolved PostgreSQL concurrency, large planning, browser E2E, restore, and native CP-SAT gates. `make verify` correctly returns failure while any required gate is unresolved; that failure is operational evidence, not a passing summary.

## Data safety and migration

The original SQLite database was backed up locally before cleanup. `schema.sql` is retained only as historical source material and is not executed because it was destructive. `boiler_reviews.db.migrate` applies ordered non-destructive migrations. `boiler_reviews.db.legacy` validates rating ranges, foreign keys, row counts, identity mappings, aggregate inputs, and unknown authorship before import. Legacy reviews are associated with an inactive explicitly unknown author rather than an invented student.

## License

MIT
