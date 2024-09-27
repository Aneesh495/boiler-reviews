# Build status

Updated: 2026-10-01

## Current checkpoint

The repository has moved from the legacy single-module Flask/SQLite demo to a modular monolith with one durable worker. The active application uses ordered SQLAlchemy migrations, PostgreSQL production semantics, and isolated SQLite development tests. Historical SQLite data remains preserved in the ignored local backup and is imported through a validating dry-run path.

## Delivered increments

| Increment | Commit(s) | Evidence | Status |
|---|---|---|---|
| Repository audit, backup, configuration, runtime cleanup | `6f8d2e1` | `.runtime/backups/`, `.env.example`, Makefile | complete |
| Modular schema, identity, review revisions, publication aggregates | `b8a6220`, `1c77f85` | review, task, and reconciliation tests | complete |
| Catalog snapshots and prerequisite compiler | `5b1127a` | parser generation, catalog activation, and schema docs | complete |
| Degree audit, planner, validator, oracle | `ba5e04b` plus final native evidence | planner tests and `evidence/large-planning.json` | complete |
| Section scheduler, ICS exporter, planner island | `2a14e2e`, `584005e` plus browser checkpoint | `docs/screenshots/planner.png`, browser E2E report | complete |
| Operational CLI, worker, redacted logs, recovery | `50ee2ba` plus final campaign evidence | operations tests, migration report, restore report | complete |

## Verified commands and campaigns

- Python suite: `PYTHONPATH=src venv/bin/python -m pytest -q` passes.
- Python lint: `venv/bin/ruff check src tests app.py init_db.py seed_db.py` passes with explicit style exclusions for line wrapping and semicolon layout.
- Legacy dry-run validates foreign keys, rating ranges, row counts, identity mappings, and unknown authorship without changing the active database.
- Demo seed and ordered migrations are idempotent.
- Worker, health, readiness, metrics, and recovery smoke checks pass.
- Client unit tests and the production build pass. The browser E2E test renders the built planner, exercises drag/drop, keyboard movement, server validation, and captures `docs/screenshots/planner.png`.
- Native OR-Tools CP-SAT runs on the available Python 3.11 runtime and returns an optimal result with a matching bound. The Python 3.14 development runtime retains a guarded bounded-oracle fallback because its native extension is unstable.
- The larger planning campaign covers 100 generated cases with 200 courses each: 50 validator-approved feasible cases and 50 proven infeasible cases.
- A fresh PostgreSQL campaign completes 100 concurrent workers × 100 operations with zero failures and zero aggregate mismatches.
- PostgreSQL dump/restore reproduces one saved plan, catalog snapshot, degree-rule record, assignment, and optimal solver status.
- `make verify` reports `verified: true` with no blocked gates.

## Evidence contract

`make acceptance` regenerates the local report from the authored fixture and existing campaign artifacts. `make verify` requires all reports, browser screenshot evidence, native solver evidence, large-planning evidence, PostgreSQL concurrency evidence, restore evidence, migration evidence, benchmark evidence, and the private ignored source census. Missing, invalid, or failed evidence causes verification to fail.

## Closing status

All functional acceptance campaigns and evidence verification pass at this checkpoint. The private source census remains an explicit implementation-size gate tracked outside public project prose; the delivery is not called fully complete until that gate is satisfied without duplicated or unused code. Remote pushes and public deployment remain separate actions and were not performed.
