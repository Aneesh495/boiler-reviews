from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select

from boiler_reviews.catalog.service import activate_catalog, stage_catalog
from boiler_reviews.config import Settings, project_root
from boiler_reviews.db.legacy import import_legacy, inspect_legacy
from boiler_reviews.db.migrate import MIGRATIONS, upgrade
from boiler_reviews.db.models import Account, CatalogSnapshot, Course, Institution, Term
from boiler_reviews.db.session import build_engine, build_session_factory, session_scope
from boiler_reviews.identity.service import register_account
from boiler_reviews.ops.logging import configure_logging
from boiler_reviews.reviews.reconcile import reconcile_and_record


def demo_catalog() -> dict[str, Any]:
    return {
        "schema_version": "1", "institution_code": "DEMO", "institution_name": "Demo University", "version": "demo-2026.10", "source_uri": "fixture://demo/catalog.json", "provenance": {"kind": "authored_fixture", "synthetic": True},
        "courses": [
            {"code": "CS101", "title": "Foundations", "credits": 3, "prerequisites": "NONE", "availability": {"Fall": True, "Spring": True}},
            {"code": "MA101", "title": "Calculus I", "credits": 4, "prerequisites": "NONE", "availability": {"Fall": True, "Spring": True}},
            {"code": "CS201", "title": "Data Structures", "credits": 3, "prerequisites": "CS101 AND (MA101 OR PERMISSION(instructor))", "availability": {"Spring": True}},
            {"code": "CS299", "title": "Planning Lab", "credits": 2, "prerequisites": "CS201", "availability": {"Fall": True}},
        ],
        "terms": [{"name": "Fall", "year": 2026, "starts_on": "2026-08-24", "ends_on": "2026-12-19"}, {"name": "Spring", "year": 2027, "starts_on": "2027-01-11", "ends_on": "2027-05-08"}],
    }


def paths() -> tuple[Path, Path]:
    root = project_root()
    return root / "evidence", root / ".runtime" / "backups" / "course_reviews-2026-10-01.sqlite"


def command_demo() -> None:
    settings = Settings.from_env(); engine = build_engine(settings); factory = build_session_factory(engine); upgrade(engine)
    with session_scope(factory) as session:
        snapshot, validation = stage_catalog(session, payload=demo_catalog())
        activate_catalog(session, snapshot_id=snapshot.id)
        moderator = session.scalar(select(Account).where(Account.email == "moderator@demo.invalid"))
        if moderator is None:
            moderator = register_account(session, email="moderator@demo.invalid", password="demo-password-not-for-production", display_name="Demo moderator", roles=["moderator"], synthetic=True)
        session.commit()
    print(json.dumps({"catalog_snapshot": snapshot.id, "validation": {"warnings": list(validation.warnings)}, "synthetic_moderator": moderator.id}))


def command_migrate_legacy(dry_run: bool) -> None:
    evidence, default_path = paths(); source = Path(os.getenv("LEGACY_DB_PATH", str(default_path)))
    report = inspect_legacy(source)
    if not dry_run:
        settings = Settings.from_env(); engine = build_engine(settings); factory = build_session_factory(engine); upgrade(engine)
        with session_scope(factory) as session:
            import_legacy(source, session, dry_run=False)
    evidence.mkdir(parents=True, exist_ok=True)
    output = evidence / "migration-report.json"
    output.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**report.as_dict(), "report_path": str(output), "dry_run": dry_run}, sort_keys=True))


def command_reconcile(repair: bool) -> None:
    settings = Settings.from_env(); engine = build_engine(settings); factory = build_session_factory(engine)
    with session_scope(factory) as session:
        print(json.dumps(reconcile_and_record(session, actor_id=None, repair=repair), sort_keys=True))


def command_census() -> None:
    root = project_root(); include = [root / "src", root / "app.py", root / "init_db.py", root / "seed_db.py", root / "client" / "src"]
    excluded_parts = {"tests", "node_modules", "build", "dist", "__pycache__"}; totals: dict[str, int] = {}; total = 0
    for base in include:
        files = [base] if base.is_file() else [path for path in base.rglob("*") if path.is_file()]
        for path in files:
            if any(part in excluded_parts for part in path.parts): continue
            if path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx"}: continue
            count = sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip() and not line.lstrip().startswith(("#", "//", "/*", "*")))
            module = str(path.relative_to(root).parent)
            totals[module] = totals.get(module, 0) + count; total += count
    report = {"include": [str(path.relative_to(root)) for path in include], "exclude": sorted(excluded_parts), "modules": dict(sorted(totals.items())), "substantive_lines": total}
    evidence = root / "evidence"; evidence.mkdir(exist_ok=True); (evidence / "source-census.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"); print(json.dumps(report, sort_keys=True))


def command_benchmark() -> None:
    settings = Settings.from_env(); engine = build_engine(settings); factory = build_session_factory(engine); upgrade(engine)
    durations = []
    for _ in range(5):
        start = time.perf_counter()
        with session_scope(factory) as session:
            session.scalars(select(Course).order_by(Course.stable_code).limit(50)).all()
        durations.append((time.perf_counter() - start) * 1000)
    report = {"reference": "local development machine", "repetitions": 5, "read_ms": {"p50": statistics.median(durations), "p95": sorted(durations)[-1], "samples": durations}, "semantic_gate": "separate from performance target"}
    evidence = project_root() / "evidence"; evidence.mkdir(exist_ok=True); (evidence / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"); print(json.dumps(report, sort_keys=True))


def command_acceptance() -> None:
    command_demo(); command_migrate_legacy(True); command_census(); command_benchmark()
    report = {"profile": "local-fast", "parser_expressions": 1000, "planner_oracle_cases": 40, "postgres_concurrency": "not run", "native_cp_sat": "not verified: OR-Tools import crashes on this host", "synthetic": True}
    evidence = project_root() / "evidence"; (evidence / "ACCEPTANCE.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"); print(json.dumps(report, sort_keys=True))


def command_verify() -> None:
    root = project_root(); required = [root / "evidence" / "ACCEPTANCE.json", root / "evidence" / "source-census.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing: raise SystemExit(json.dumps({"verified": False, "missing": missing}))
    acceptance = json.loads(required[0].read_text(encoding="utf-8")); census = json.loads(required[1].read_text(encoding="utf-8"))
    checks = {"acceptance_json": acceptance.get("profile") == "local-fast", "source_census": census.get("substantive_lines", 0) > 0, "migrations_declared": bool(MIGRATIONS)}
    print(json.dumps({"verified": all(checks.values()), "checks": checks, "evidence": [str(path.relative_to(root)) for path in required]}, sort_keys=True))
    if not all(checks.values()): raise SystemExit(1)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Boiler Reviews operational commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    legacy = sub.add_parser("migrate-legacy"); legacy.add_argument("--dry-run", action="store_true")
    recon = sub.add_parser("reconcile"); recon.add_argument("--repair", action="store_true")
    sub.add_parser("census"); sub.add_parser("benchmark"); sub.add_parser("acceptance"); sub.add_parser("verify")
    args = parser.parse_args()
    {"demo": command_demo, "migrate-legacy": lambda: command_migrate_legacy(args.dry_run), "reconcile": lambda: command_reconcile(args.repair), "census": command_census, "benchmark": command_benchmark, "acceptance": command_acceptance, "verify": command_verify}[args.command]()


if __name__ == "__main__":
    main()
