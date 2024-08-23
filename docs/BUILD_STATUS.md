# Build status

Updated: 2026-10-01

## Current checkpoint

The repository was audited at commit `8104319`. The legacy application is a single Flask module over SQLite with four tables and twelve seeded review rows. The tracked runtime database and bytecode were backed up under the ignored `.runtime/backups/` directory and removed from version control. The new modular package and migration work are next.

## Baseline evidence

- Branch: `main`, aligned with `origin/main` at the audit checkpoint.
- Legacy database shape: `courses`, `semesters`, `reviews`, `course_stats`.
- Legacy row counts: 4 courses, 3 semesters, 12 reviews, 4 aggregate rows.
- Baseline route smoke could not run with system Python because Flask is not installed there; the repository virtualenv has Flask 3.1.3.
- No root test suite or Makefile existed before this checkpoint.
- The legacy database backup is local-only and intentionally ignored.

## Delivered increments

| Increment | Status | Evidence | Remaining gate |
|---|---|---|---|
| Repository audit and legacy backup | complete | this file; `.runtime/backups/` | none |
| Modular package and safe configuration skeleton | in progress | source tree and Makefile | migration and application checks |

## Verification commands

Commands are recorded with their result as the implementation proceeds. A command is not considered evidence until its output is stored in `evidence/` or a checked-in report references the exact output.

## Next action

Implement the versioned SQLAlchemy/Alembic schema and an idempotent legacy dry-run importer before changing the active application entry point.
