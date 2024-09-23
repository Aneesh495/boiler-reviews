from __future__ import annotations

from typing import Any

from boiler_reviews.ops.logging import Metrics


def render_metrics(metrics: Metrics) -> str:
    snapshot = metrics.snapshot()
    lines: list[str] = []
    for name, value in sorted(snapshot["counters"].items()):
        metric = name.replace(":", "_").replace("-", "_")
        lines.append(f"boiler_reviews_{metric} {value}")
    for name, values in sorted(snapshot["timings_ms"].items()):
        metric = name.replace(":", "_").replace("-", "_")
        lines.append(f"boiler_reviews_{metric}_count {values['count']}")
        lines.append(f"boiler_reviews_{metric}_p50_ms {values['p50']}")
        lines.append(f"boiler_reviews_{metric}_p95_ms {values['p95']}")
    return "\n".join(lines) + ("\n" if lines else "")


def metric_payload(metrics: Metrics) -> dict[str, Any]:
    return metrics.snapshot()
