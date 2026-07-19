"""In-process operational metrics for governed agent tool calls.

The registry is intentionally dependency-free so it works on Render web and
worker processes without requiring a metrics sidecar. Metrics are process-local;
OpenTelemetry remains the cross-process export path.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class _ToolStats:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    durations_ms: deque[float] = field(default_factory=lambda: deque(maxlen=200))
    failure_categories: Counter[str] = field(default_factory=Counter)


class ToolMetricsRegistry:
    """Thread-safe bounded metrics registry keyed by governed tool name."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._stats: dict[str, _ToolStats] = defaultdict(_ToolStats)

    def record(
        self,
        *,
        tool_name: str,
        success: bool,
        duration_ms: float,
        failure_category: str | None = None,
    ) -> None:
        with self._lock:
            stats = self._stats[tool_name]
            stats.calls += 1
            stats.successes += int(success)
            stats.failures += int(not success)
            stats.total_duration_ms += duration_ms
            stats.max_duration_ms = max(stats.max_duration_ms, duration_ms)
            stats.durations_ms.append(duration_ms)
            if failure_category:
                stats.failure_categories[failure_category] += 1

    def snapshot(
        self,
        *,
        failure_rate_threshold: float,
        latency_threshold_ms: float,
    ) -> dict[str, Any]:
        with self._lock:
            tools: dict[str, Any] = {}
            total_calls = 0
            total_failures = 0
            degraded_tools: list[str] = []

            for tool_name, stats in sorted(self._stats.items()):
                total_calls += stats.calls
                total_failures += stats.failures
                failure_rate = stats.failures / stats.calls if stats.calls else 0.0
                average_ms = stats.total_duration_ms / stats.calls if stats.calls else 0.0
                p95_ms = _percentile(list(stats.durations_ms), 0.95)
                degraded = (
                    failure_rate > failure_rate_threshold
                    or p95_ms > latency_threshold_ms
                )
                if degraded:
                    degraded_tools.append(tool_name)
                tools[tool_name] = {
                    "calls": stats.calls,
                    "successes": stats.successes,
                    "failures": stats.failures,
                    "failure_rate": round(failure_rate, 4),
                    "average_duration_ms": round(average_ms, 2),
                    "p95_duration_ms": round(p95_ms, 2),
                    "max_duration_ms": round(stats.max_duration_ms, 2),
                    "failure_categories": dict(stats.failure_categories),
                    "status": "degraded" if degraded else "healthy",
                }

            overall_failure_rate = total_failures / total_calls if total_calls else 0.0
            return {
                "status": "degraded" if degraded_tools else "healthy",
                "total_calls": total_calls,
                "total_failures": total_failures,
                "failure_rate": round(overall_failure_rate, 4),
                "degraded_tools": degraded_tools,
                "tools": tools,
            }

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile)))
    return ordered[index]


tool_metrics = ToolMetricsRegistry()
