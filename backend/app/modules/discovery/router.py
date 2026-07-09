"""Discovery — FastAPI router for network discovery (Option B).

Exposes:
  - ``GET  /api/v1/discovery/endpoints``           — list discovered endpoints.
  - ``GET  /api/v1/discovery/endpoints/{id}``      — get one endpoint.
  - ``POST /api/v1/discovery/analyze``             — analyze a HAR + store candidates.
  - ``POST /api/v1/discovery/endpoints/{id}/mark-stale``  — mark an endpoint stale.
  - ``GET  /api/v1/discovery/stats``               — aggregate stats.

All endpoints sit behind the app's JWT auth middleware (the ``/api/v1``
prefix is not in ``PUBLIC_PREFIXES``).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.discovery.endpoint_store import (
    get_endpoint, list_endpoints, mark_stale, store_discovered_endpoints,
)
from ...core.discovery.har_analyzer import analyze_har

router = APIRouter(prefix="/discovery", tags=["discovery"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class AnalyzeBody(BaseModel):
    """POST body for /discovery/analyze."""
    har: dict[str, Any]
    actionName: str
    connectorId: str | None = None


class MarkStaleBody(BaseModel):
    """POST body for /discovery/endpoints/{id}/mark-stale."""
    reason: str


# ---------------------------------------------------------------------------
# GET /discovery/endpoints
# ---------------------------------------------------------------------------


@router.get("/endpoints")
async def list_endpoints_endpoint(
    actionName: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List discovered endpoints, optionally filtered by action / status."""
    items = await list_endpoints(action_name=actionName, status=status)
    return {"endpoints": items, "total": len(items)}


# ---------------------------------------------------------------------------
# GET /discovery/endpoints/{id}
# ---------------------------------------------------------------------------


@router.get("/endpoints/{endpoint_id}")
async def get_endpoint_endpoint(endpoint_id: str) -> dict[str, Any]:
    """Fetch a single discovered endpoint by id."""
    ep = await get_endpoint(endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="endpoint not found")
    return ep


# ---------------------------------------------------------------------------
# POST /discovery/analyze
# ---------------------------------------------------------------------------


@router.post("/analyze")
async def analyze_endpoint(body: AnalyzeBody) -> dict[str, Any]:
    """Analyze a HAR capture and store the discovered endpoint candidates.

    Returns the created endpoint rows (top 3 by business score). This is
    the same flow that runs automatically when a recording is compiled,
    exposed as a manual trigger for operators / debugging.
    """
    if not body.har or not body.actionName:
        raise HTTPException(
            status_code=400, detail="har and actionName are required",
        )
    try:
        candidates = analyze_har(
            body.har, body.actionName, body.connectorId
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"HAR analysis failed: {exc}",
        )
    if not candidates:
        return {"created": [], "count": 0}
    # Persist candidates and read them back so we return the full rows
    # (with ids, timestamps, etc.) rather than the bare dataclass shape.
    stored = await store_discovered_endpoints(
        candidates, body.actionName, body.connectorId
    )
    # Re-list to fetch the freshly-stored rows for this action.
    rows = await list_endpoints(action_name=body.actionName)
    return {"created": rows[:len(candidates)], "count": stored}


# ---------------------------------------------------------------------------
# POST /discovery/endpoints/{id}/mark-stale
# ---------------------------------------------------------------------------


@router.post("/endpoints/{endpoint_id}/mark-stale")
async def mark_stale_endpoint(
    endpoint_id: str, body: MarkStaleBody,
) -> dict[str, Any]:
    """Mark a discovered endpoint as stale (skipped on future replays)."""
    existing = await get_endpoint(endpoint_id)
    if not existing:
        raise HTTPException(status_code=404, detail="endpoint not found")
    await mark_stale(endpoint_id, body.reason or "manual")
    updated = await get_endpoint(endpoint_id)
    return updated or {"id": endpoint_id, "status": "stale"}


# ---------------------------------------------------------------------------
# GET /discovery/stats
# ---------------------------------------------------------------------------


@router.get("/stats")
async def stats_endpoint() -> dict[str, Any]:
    """Aggregate stats across all discovered endpoints."""
    all_eps = await list_endpoints()
    total = len(all_eps)
    active = sum(1 for e in all_eps if e.get("status") == "active")
    stale = sum(1 for e in all_eps if e.get("status") == "stale")
    total_replays = sum(int(e.get("timesReplayed", 0)) for e in all_eps)
    total_succeeded = sum(int(e.get("timesSucceeded", 0)) for e in all_eps)
    success_rate = (
        round(total_succeeded / total_replays, 4) if total_replays else 0.0
    )
    # Weighted average latency (weighted by replay count).
    total_weighted_lat = sum(
        int(e.get("avgLatencyMs", 0)) * int(e.get("timesReplayed", 0))
        for e in all_eps
    )
    avg_latency = (
        int(total_weighted_lat / total_replays) if total_replays else 0
    )
    return {
        "totalEndpoints": total,
        "activeEndpoints": active,
        "staleEndpoints": stale,
        "totalReplays": total_replays,
        "successRate": success_rate,
        "avgLatencyMs": avg_latency,
    }
