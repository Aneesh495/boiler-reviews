from __future__ import annotations

import argparse
import json
import os
import socket
from typing import Any

from sqlalchemy.orm import Session

from boiler_reviews.config import Settings
from boiler_reviews.db.session import build_engine, build_session_factory, session_scope
from boiler_reviews.ops.logging import configure_logging
from boiler_reviews.ops.recovery import reconcile_expired_tasks
from boiler_reviews.planning.api import plan_result_payload, request_from_json
from boiler_reviews.planning.solver import solve
from boiler_reviews.reviews.reconcile import reconcile_and_record
from boiler_reviews.tasks.queue import TaskLease, TaskWorker


def handlers() -> dict[str, Any]:
    def solve_handler(session: Session, task: Any, lease: TaskLease) -> dict[str, Any]:
        request = request_from_json(task.payload_json)
        result = solve(request, alternatives=int(task.payload_json.get("alternatives", 1)))[0]
        return plan_result_payload(result)

    def reconcile_handler(session: Session, task: Any, lease: TaskLease) -> dict[str, Any]:
        return reconcile_and_record(session, actor_id=task.account_id, repair=bool(task.payload_json.get("repair", False)))

    def projection_handler(session: Session, task: Any, lease: TaskLease) -> dict[str, Any]:
        return {"projection": "rebuild requested", "task_id": task.id}

    return {"solve": solve_handler, "aggregate_reconcile": reconcile_handler, "projection_rebuild": projection_handler}


def run_once() -> bool:
    settings = Settings.from_env()
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    with session_scope(factory) as session:
        reconcile_expired_tasks(session)
    worker = TaskWorker(factory, handlers(), owner=f"{socket.gethostname()}:{os.getpid()}", lease_seconds=settings.task_lease_seconds)
    return worker.run_once()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process one or more durable Boiler Reviews tasks")
    parser.add_argument("--once", action="store_true", help="claim at most one task")
    parser.add_argument("--iterations", type=int, default=1)
    args = parser.parse_args()
    configure_logging()
    processed = 0
    for _ in range(max(1, args.iterations)):
        if run_once():
            processed += 1
        elif args.once:
            break
    print(json.dumps({"processed": processed}))


if __name__ == "__main__":
    main()
