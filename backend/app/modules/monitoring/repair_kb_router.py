"""Repair Knowledge Base - FastAPI router for the cross-client repair flywheel.

Exposes:
  - ``GET  /api/v1/monitoring/repair-kb``             - list KB entries.
  - ``GET  /api/v1/monitoring/repair-kb/{id}``        - get one KB entry.
  - ``GET  /api/v1/monitoring/repair-kb/stats``       - aggregate KB stats
    (size, active entries, total successes, MTTR trend, top domains).
  - ``POST /api/v1/monitoring/repair-kb/{id}/deprecate`` - mark a KB
    entry ``status="deprecated"`` so it's excluded from future searches.

All endpoints sit behind the app's JWT auth middleware (the ``/api/v1``
prefix is not in ``PUBLIC_PREFIXES``).

The KB is the defensive moat: every rupture repaired makes the next one
faster for everyone. This router gives operators visibility into what's
been learned and a kill-switch for entries that have gone stale.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from ...infrastructure.prisma_repositories import (
    repair_kb_get_by_id, repair_kb_list, repair_kb_set_status,
)

router = APIRouter(prefix="/monitoring/repair-kb", tags=["repair-kb"])


def _with_success_rate(entry: dict) -> dict:
    """Attach a computed ``successRate`` to a KB entry dict."""
    s = int(entry.get("successCount", 0) or 0)
    f = int(entry.get("failureCount", 0) or 0)
    total = s + f
    entry = dict(entry)
    entry["successRate"] = round(s / total, 4) if total else 0.0
    return entry


# ---------------------------------------------------------------------------
# GET /monitoring/repair-kb
# ---------------------------------------------------------------------------


@router.get("")
@router.get("/")
async def list_kb_endpoint(
    targetDomain: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List KB entries, optionally filtered by target domain / status.

    Returns each entry with a computed ``successRate = successCount /
    (successCount + failureCount)`` so the frontend can sort without
    re-doing the division.
    """
    items = await repair_kb_list(target_domain=targetDomain, status=status)
    return {
        "entries": [_with_success_rate(e) for e in items],
        "total": len(items),
    }


# ---------------------------------------------------------------------------
# GET /monitoring/repair-kb/stats  (declared BEFORE /{id} so /stats isn't
# shadowed by the {id} path parameter)
# ---------------------------------------------------------------------------


@router.get("/stats")
async def stats_endpoint() -> dict[str, Any]:
    """Aggregate Repair-KB stats for the flywheel dashboard.

    Returns:
    - ``totalEntries``        - total KB size.
    - ``activeEntries``       - entries with ``status="active"``.
    - ``totalSuccesses``      - sum of ``successCount`` across all entries.
    - ``totalAutoApplied``    - sum of ``autoAppliedCount``.
    - ``avgConfidence``       - mean confidence of active entries (0 if none).
    - ``mttrTrend``           - list of ``{bucket, mttrMs}`` points for the
      last 7 days. ``mttrMs`` is null for every bucket because real MTTR
      requires incident-start vs incident-resolved timestamp pairs, which
      the RepairKnowledge row does not store yet (planned). The buckets
      are still returned so the frontend can render the time axis.
    - ``mttrNote``            - human-readable explanation of why MTTR is
      null (so the UI can surface the limitation rather than hiding it).
    - ``topDomains``          - top 5 ``targetDomain``s by ``successCount``.
    """
    all_entries = await repair_kb_list()
    total = len(all_entries)
    active = [e for e in all_entries if e.get("status") == "active"]
    total_successes = sum(int(e.get("successCount", 0) or 0) for e in all_entries)
    total_auto = sum(int(e.get("autoAppliedCount", 0) or 0) for e in all_entries)
    avg_confidence = (
        round(sum(float(e.get("confidence", 0) or 0) for e in active) / len(active), 4)
        if active else 0.0
    )

    # ---- MTTR trend -----------------------------------------------------
    # Real MTTR needs (incident_detected_at, incident_resolved_at) pairs.
    # The RepairKnowledge row only stores createdAt / updatedAt /
    # lastUsedAt, none of which is an incident-start timestamp, so any
    # number we computed here would be fabricated. Previously this
    # block used the synthetic formula ``max(200, 1200 - 80*success)``
    # and a "monotonically improving" fallback when the KB was empty,
    # which produced a fake "flywheel accelerating" curve. We now
    # return null for every bucket instead, and surface mttrNote so
    # the UI can explain the gap to operators.
    now = datetime.utcnow()
    mttr_trend: list[dict[str, Any]] = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        mttr_trend.append({"bucket": day, "mttrMs": None})

    # ---- Top domains ----------------------------------------------------
    domain_totals: dict[str, int] = defaultdict(int)
    for e in all_entries:
        d = e.get("targetDomain") or "unknown"
        domain_totals[d] += int(e.get("successCount", 0) or 0)
    top_domains = sorted(
        ({"domain": d, "successCount": n} for d, n in domain_totals.items()),
        key=lambda x: x["successCount"], reverse=True,
    )[:5]

    return {
        "totalEntries": total,
        "activeEntries": len(active),
        "totalSuccesses": total_successes,
        "totalAutoApplied": total_auto,
        "avgConfidence": avg_confidence,
        "mttrTrend": mttr_trend,
        "mttrNote": "MTTR tracking requires incident timestamps (planned)",
        "topDomains": top_domains,
    }


# ---------------------------------------------------------------------------
# GET /monitoring/repair-kb/{id}
# ---------------------------------------------------------------------------


@router.get("/{entry_id}")
async def get_kb_endpoint(entry_id: str) -> dict[str, Any]:
    """Fetch a single RepairKnowledge entry by id."""
    entry = await repair_kb_get_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="repair-kb entry not found")
    return _with_success_rate(entry)


# ---------------------------------------------------------------------------
# POST /monitoring/repair-kb/{id}/deprecate
# ---------------------------------------------------------------------------


@router.post("/{entry_id}/deprecate")
async def deprecate_kb_endpoint(entry_id: str) -> dict[str, Any]:
    """Mark a RepairKnowledge entry as ``status="deprecated"``.

    Deprecated entries are excluded from ``repair_kb_search`` (which
    filters on ``status="active"``), so they won't be returned by
    ``query_kb`` for future failures. The entry is preserved (not
    deleted) so its historical success/failure counts remain available
    for analytics.
    """
    existing = await repair_kb_get_by_id(entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="repair-kb entry not found")
    updated = await repair_kb_set_status(entry_id, "deprecated")
    return _with_success_rate(updated or existing)
