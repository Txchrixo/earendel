"""Monitoring — time-series service: deterministic hourly success-rate series.

Returns a 24-point series (one per hour) of success rate + execution count,
ending at the live value from the current executions. Used by the dashboard
sparkline and the monitoring reliability trend chart.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ...core.domain.enums import ExecutionStatus
from .repository import list_executions


def _hour_bucket(ts: datetime) -> datetime:
    """Truncate a datetime to the hour."""
    return ts.replace(minute=0, second=0, microsecond=0)


async def timeseries(hours: int = 24) -> dict[str, Any]:
    """Build a hourly success-rate + execution-count series for the last N hours.

    Each point: {ts, successRate, total, successes, failures}. The last point
    reflects the live current-hour data.

    Phase 6: synthetic baseline data has been removed. The chart now shows
    REAL execution data only — including canary executions from the scheduler.
    Hours with no executions show successRate=1.0 and total=0 (honest "no data").
    """
    now = datetime.utcnow()
    buckets: dict[datetime, dict[str, int]] = {}
    for h in range(hours):
        b = _hour_bucket(now - timedelta(hours=hours - 1 - h))
        buckets[b] = {"total": 0, "successes": 0, "failures": 0}

    # Bucket actual executions by startedAt hour.
    exe_all = await list_executions()
    for e in exe_all:
        b = _hour_bucket(e.startedAt)
        if b in buckets:
            buckets[b]["total"] += 1
            if e.status == ExecutionStatus.success:
                buckets[b]["successes"] += 1
            elif e.status in (ExecutionStatus.failed, ExecutionStatus.degraded):
                buckets[b]["failures"] += 1

    # Phase 6: no more synthetic baseline — real data only.
    series: list[dict[str, Any]] = []
    for b, counts in buckets.items():
        total = counts["total"]
        successes = counts["successes"]
        # When there are no executions, show successRate=1.0 (no failures)
        # rather than 0.0 (which would look like everything is broken).
        rate = round(successes / total, 3) if total > 0 else 1.0
        series.append({
            "ts": b.isoformat() + "Z",
            "hourLabel": b.strftime("%H:00"),
            "successRate": rate,
            "total": total,
            "successes": successes,
            "failures": total - successes,
        })

    return {
        "points": series,
        "hours": hours,
        "generatedAt": now.isoformat() + "Z",
    }
