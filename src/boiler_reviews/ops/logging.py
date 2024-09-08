from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

_SENSITIVE = re.compile(r"(password|secret|token|authorization|cookie|email)", re.IGNORECASE)


class RedactingJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {"message", "args", "msg", "exc_info", "exc_text", "stack_info"}:
                continue
            if _SENSITIVE.search(key):
                continue
            if key in {"request_id", "task_id", "status", "duration_ms", "event"}:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingJsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


@dataclass(slots=True)
class Metrics:
    counters: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, list[float]] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def observe(self, name: str, duration_ms: float) -> None:
        self.timings_ms.setdefault(name, []).append(duration_ms)

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {"counters": dict(self.counters), "timings_ms": {}}
        for name, values in self.timings_ms.items():
            ordered = sorted(values)
            result["timings_ms"][name] = {"count": len(values), "p50": ordered[len(ordered) // 2], "p95": ordered[min(len(ordered) - 1, int(len(ordered) * .95))]}
        return result
