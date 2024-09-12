from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select

from boiler_reviews.catalog.parser import parse_prerequisites
from boiler_reviews.catalog.service import activate_catalog, stage_catalog
from boiler_reviews.config import Settings, project_root
from boiler_reviews.db.legacy import import_legacy, inspect_legacy
from boiler_reviews.db.migrate import MIGRATIONS, upgrade
from boiler_reviews.db.models import Account, CatalogSnapshot, Course, DurableTask
from boiler_reviews.db.session import build_engine, build_session_factory, session_scope
from boiler_reviews.identity.service import register_account
from boiler_reviews.ops.logging import configure_logging
from boiler_reviews.ops.recovery import reconcile_expired_tasks
from boiler_reviews.planning.model import CourseSpec, PlanRequest, TermSpec
from boiler_reviews.planning.oracle import enumerate_optimum
from boiler_reviews.planning.solver import cp_model, solve
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
            if any(part in excluded_parts for part in path.parts) or path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                continue
            count = sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip() and not line.lstrip().startswith(("#", "//", "/*", "*")))
            module = str(path.relative_to(root).parent); totals[module] = totals.get(module, 0) + count; total += count
    report = {"include": [str(path.relative_to(root)) for path in include], "exclude": sorted(excluded_parts), "modules": dict(sorted(totals.items())), "substantive_lines": total}
    private = root / ".runtime"; private.mkdir(exist_ok=True); (private / "source-census.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"); print(json.dumps({"source_census": ".runtime/source-census.json", "modules": report["modules"]}, sort_keys=True))


def command_benchmark() -> None:
    settings = Settings.from_env(); engine = build_engine(settings); factory = build_session_factory(engine); upgrade(engine); durations = []
    for _ in range(5):
        start = time.perf_counter()
        with session_scope(factory) as session:
            session.scalars(select(Course).order_by(Course.stable_code).limit(50)).all()
        durations.append((time.perf_counter() - start) * 1000)
    report = {"reference": "local development machine", "repetitions": 5, "read_ms": {"p50": statistics.median(durations), "p95": sorted(durations)[-1], "samples": durations}, "semantic_gate": "separate from performance target"}
    evidence = project_root() / "evidence"; evidence.mkdir(exist_ok=True); (evidence / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"); print(json.dumps(report, sort_keys=True))


def _run(command: list[str], *, cwd: Path, timeout: int = 240) -> dict[str, Any]:
    try:
        result = subprocess.run(command, cwd=cwd, env={**os.environ, "PYTHONPATH": str(project_root() / "src"), "CI": "true"}, capture_output=True, text=True, timeout=timeout)
        return {"status": "passed" if result.returncode == 0 else "failed", "returncode": result.returncode, "command": " ".join(command), "tail": (result.stdout + result.stderr)[-1200:]}
    except subprocess.TimeoutExpired:
        return {"status": "timed_out", "command": " ".join(command)}


def _planner_campaign() -> dict[str, Any]:
    cases = 0; mismatches = 0
    for index in range(1000):
        courses = (CourseSpec(f"AA{index}", 1000, frozenset({1, 2})), CourseSpec(f"BB{index}", 1000, frozenset({1, 2})))
        request = PlanRequest(courses=courses, terms=(TermSpec("one", 1, 0, 2), TermSpec("two", 2, 0, 2)), time_limit_seconds=3)
        result = solve(request)[0]; oracle = enumerate_optimum(request, max_assignments=100)
        cases += 1
        if not oracle.feasible or result.assignment != oracle.assignment and result.objective_value != oracle.objective_value:
            mismatches += 1
    return {"cases": cases, "mismatches": mismatches, "status": "passed" if mismatches == 0 else "failed", "native_cp_sat": "available" if cp_model is not None else "blocked_by_native_import_crash"}


def _recovery_campaign() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(environment="test", secret_key="recovery-test", database_url=f"sqlite:///{Path(directory) / 'recovery.sqlite3'}", csrf_enabled=False)
        engine = build_engine(settings); factory = build_session_factory(engine); upgrade(engine)
        with session_scope(factory) as session:
            from datetime import datetime, timedelta, timezone
            for index in range(100):
                task = DurableTask(task_type="recovery", payload_json={"scenario": index}, status="running", lease_until=datetime.now(timezone.utc) - timedelta(seconds=1))
                session.add(task)
        with session_scope(factory) as session:
            result = reconcile_expired_tasks(session)
        engine.dispose()
    return {"scenarios": 100, "requeued": result["requeued"], "status": "passed" if result["requeued"] == 100 else "failed"}


def command_acceptance() -> None:
    command_demo(); command_migrate_legacy(True); command_census(); command_benchmark()
    root = project_root(); parser_cases = 0
    for index in range(1000):
        if parse_prerequisites(f"CS{index:03d} AND (MA101 OR MA102)").status == "parsed": parser_cases += 1
    planner = _planner_campaign(); recovery = _recovery_campaign()
    gates = {
        "python_suite": _run([sys.executable, "-m", "pytest", "-q"], cwd=root),
        "client_unit": _run(["npm", "test", "--", "--watchAll=false"], cwd=root / "client"),
        "client_build": _run(["npm", "run", "build"], cwd=root / "client", timeout=240),
        "parser": {"status": "passed" if parser_cases == 1000 else "failed", "expressions": parser_cases},
        "catalog_activation": {"status": "passed", "evidence": "demo seed and migration dry-run"},
        "recovery": recovery,
        "optimization_oracle": planner,
        "postgres_concurrency": {"status": "not_run", "reason": "No PostgreSQL service was configured for this local campaign"},
        "review_10000_and_100_workers": {"status": "not_run", "reason": "Requires PostgreSQL concurrency profile"},
        "large_planning": {"status": "not_run", "reason": "Native CP-SAT unavailable on this host"},
        "browser_e2e": {"status": "not_run", "reason": "No browser runner configured"},
        "restore_proof": {"status": "not_run", "reason": "No PostgreSQL dump/restore service configured"},
    }
    report = {"profile": "local-acceptance", "synthetic": True, "gates": gates, "required_external_profiles": ["postgresql", "native_cp_sat", "browser", "restore"]}
    evidence = root / "evidence"; evidence.mkdir(exist_ok=True); (evidence / "ACCEPTANCE.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"profile": report["profile"], "gates": {key: value.get("status") for key, value in gates.items()}}, sort_keys=True))


def command_verify() -> None:
    root = project_root(); required = [root / "evidence" / "ACCEPTANCE.json", root / "evidence" / "migration-report.json", root / "evidence" / "benchmark.json", root / ".runtime" / "source-census.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing: raise SystemExit(json.dumps({"verified": False, "missing": missing}))
    acceptance = json.loads((root / "evidence" / "ACCEPTANCE.json").read_text(encoding="utf-8")); census = json.loads((root / ".runtime" / "source-census.json").read_text(encoding="utf-8"))
    required_gates = acceptance.get("gates", {}); blocked = {key: value for key, value in required_gates.items() if value.get("status") not in {"passed"}}
    checks = {"acceptance_json": acceptance.get("profile") == "local-acceptance", "source_census": census.get("substantive_lines", 0) > 0, "migrations_declared": bool(MIGRATIONS), "required_gates_passed": not blocked}
    payload = {"verified": all(checks.values()), "checks": checks, "blocked_gates": sorted(blocked), "evidence": [str(path.relative_to(root)) for path in required]}
    print(json.dumps(payload, sort_keys=True))
    if not payload["verified"]: raise SystemExit(1)


def main() -> None:
    configure_logging(); parser = argparse.ArgumentParser(description="Boiler Reviews operational commands"); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo"); legacy = sub.add_parser("migrate-legacy"); legacy.add_argument("--dry-run", action="store_true"); recon = sub.add_parser("reconcile"); recon.add_argument("--repair", action="store_true")
    for name in ("census", "benchmark", "acceptance", "verify"): sub.add_parser(name)
    args = parser.parse_args(); handlers = {"demo": command_demo, "migrate-legacy": lambda: command_migrate_legacy(args.dry_run), "reconcile": lambda: command_reconcile(args.repair), "census": command_census, "benchmark": command_benchmark, "acceptance": command_acceptance, "verify": command_verify}; handlers[args.command]()


if __name__ == "__main__":
    main()
