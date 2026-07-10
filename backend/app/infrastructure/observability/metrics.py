"""Phase 9 — Prometheus metrics for observability.

Exposes counters, histograms, and gauges for:
- Execution count by adapter + status
- Execution duration by adapter
- Repair KB hits/misses
- Canary run results
- Discovered endpoint count
- Published action calls (registry)

Metrics are exposed at GET /api/v1/metrics (Prometheus text format).
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# --------------------------------------------------------------------------- #
# Counters
# --------------------------------------------------------------------------- #

executions_total = Counter(
    "earendel_executions_total",
    "Total executions by adapter and status",
    ["adapter", "status", "caller"],
)

repair_kb_queries_total = Counter(
    "earendel_repair_kb_queries_total",
    "Repair KB queries (hit/miss)",
    ["result"],  # hit, miss
)

repair_kb_stores_total = Counter(
    "earendel_repair_kb_stores_total",
    "Repair KB stores",
)

canary_runs_total = Counter(
    "earendel_canary_runs_total",
    "Canary runs by result",
    ["result"],  # success, failure
)

published_action_calls_total = Counter(
    "earendel_published_action_calls_total",
    "Published action calls (registry consumption)",
    ["published_action_id", "status"],
)

# --------------------------------------------------------------------------- #
# Histograms
# --------------------------------------------------------------------------- #

execution_duration_ms = Histogram(
    "earendel_execution_duration_ms",
    "Execution duration in milliseconds by adapter",
    ["adapter"],
    buckets=(50, 100, 200, 500, 1000, 2000, 5000, 10000, 30000),
)

# --------------------------------------------------------------------------- #
# Gauges
# --------------------------------------------------------------------------- #

discovered_endpoints_active = Gauge(
    "earendel_discovered_endpoints_active",
    "Number of active discovered endpoints",
)

repair_kb_entries = Gauge(
    "earendel_repair_kb_entries",
    "Number of repair KB entries (active)",
)

published_actions_total = Gauge(
    "earendel_published_actions_total",
    "Number of published actions in the registry",
)

tenant_count = Gauge(
    "earendel_tenant_count",
    "Number of tenants",
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def record_execution(adapter: str, status: str, caller: str, duration_ms: int) -> None:
    """Record an execution result."""
    executions_total.labels(adapter=adapter, status=status, caller=caller).inc()
    execution_duration_ms.labels(adapter=adapter).observe(duration_ms)


def record_repair_kb_query(result: str) -> None:
    """Record a repair KB query (hit or miss)."""
    repair_kb_queries_total.labels(result=result).inc()


def record_canary(result: str) -> None:
    """Record a canary run result."""
    canary_runs_total.labels(result=result).inc()


def get_metrics() -> tuple[str, str]:
    """Return (metrics_text, content_type) for the Prometheus endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
