from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration with an explicit production secret contract."""

    environment: str
    secret_key: str
    database_url: str
    connect_timeout_seconds: int = 5
    query_timeout_ms: int = 5000
    database_pool_size: int = 20
    database_max_overflow: int = 30
    planner_time_limit_seconds: int = 15
    worker_poll_seconds: float = 1.0
    task_lease_seconds: int = 60
    csrf_enabled: bool = True

    @classmethod
    def from_env(cls) -> Settings:
        environment = os.getenv("APP_ENV", "development").strip().lower()
        secret_key = os.getenv("SECRET_KEY", "").strip()
        if environment == "production" and len(secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be supplied with at least 32 characters in production")
        if not secret_key:
            secret_key = secrets.token_urlsafe(32)
        database_url = os.getenv(
            "DATABASE_URL", "sqlite:///instance/boiler_reviews.sqlite3"
        ).strip()
        return cls(
            environment=environment,
            secret_key=secret_key,
            database_url=database_url,
            connect_timeout_seconds=int(os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "5")),
            query_timeout_ms=int(os.getenv("DATABASE_QUERY_TIMEOUT_MS", "5000")),
            database_pool_size=int(os.getenv("DATABASE_POOL_SIZE", "20")),
            database_max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "30")),
            planner_time_limit_seconds=int(os.getenv("PLANNER_TIME_LIMIT_SECONDS", "15")),
            worker_poll_seconds=float(os.getenv("WORKER_POLL_SECONDS", "1")),
            task_lease_seconds=int(os.getenv("TASK_LEASE_SECONDS", "60")),
            csrf_enabled=environment != "test" or os.getenv("DISABLE_CSRF", "0") != "1",
        )

    def ensure_local_directories(self, root: Path) -> None:
        if self.database_url.startswith("sqlite:///"):
            (root / "instance").mkdir(parents=True, exist_ok=True)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
