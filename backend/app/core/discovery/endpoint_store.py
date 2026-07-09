"""Endpoint store — thin async service layer over the Prisma repository.

Persists :class:`DiscoveredEndpointCandidate` instances to the
``DiscoveredEndpoint`` table and exposes the lookup / mutation helpers the
``internal_route`` adapter needs at runtime.

This layer exists so the adapter + routers don't import the SQLAlchemy
repository directly — they go through a small, mockable surface that knows
how to (de)serialize the JSON-stringified columns (bodyTemplate,
fieldMapping, responseShape, headersTemplate).
"""
from __future__ import annotations

import json
from typing import Any

from ...infrastructure.prisma_repositories import (
    discovered_endpoint_delete,
    discovered_endpoint_get,
    discovered_endpoint_get_best,
    discovered_endpoint_list,
    discovered_endpoint_mark_stale,
    discovered_endpoint_put,
    discovered_endpoint_record_replay,
)
from ...shared.ids import new_id
from .har_analyzer import DiscoveredEndpointCandidate


def _candidate_to_row(
    candidate: DiscoveredEndpointCandidate,
) -> dict[str, Any]:
    """Convert a candidate dataclass into the dict shape ``discovered_endpoint_put`` expects."""
    return {
        "id": new_id("dep"),
        "actionName": candidate.action_name,
        "connectorId": candidate.connector_id,
        "method": candidate.method,
        "url": candidate.url,
        "urlPattern": candidate.url_pattern,
        "bodyTemplate": json.dumps(candidate.body_template or {}),
        "headersTemplate": json.dumps(candidate.headers_template or {}),
        "cookieEnvVar": candidate.cookie_env_var,
        "fieldMapping": json.dumps(candidate.field_mapping or {}),
        "responseShape": json.dumps(candidate.response_shape or {}),
        "businessScore": float(candidate.business_score),
        "clusterSize": int(candidate.cluster_size),
        "status": "active",
        "staleReason": None,
        "timesReplayed": 0,
        "timesSucceeded": 0,
        "timesFailed": 0,
        "avgLatencyMs": 0,
        "discoveredFrom": candidate.discovered_from,
        "lastReplayedAt": None,
    }


async def store_discovered_endpoints(
    candidates: list[DiscoveredEndpointCandidate],
    action_name: str,
    connector_id: str | None,
) -> int:
    """Persist candidates via ``discovered_endpoint_put``.

    Args:
        candidates: Output of :func:`analyze_har`.
        action_name: Sanity stamp — overrides ``candidate.action_name`` so the
            caller can't accidentally persist under the wrong action.
        connector_id: Optional override for the connector id.

    Returns:
        The number of candidates actually stored.
    """
    stored = 0
    for cand in candidates:
        # Stamp the caller-provided action_name / connector_id so the API
        # endpoint (/discovery/analyze) can't be tricked into persisting
        # under a different action than the one it claimed.
        cand.action_name = action_name
        if connector_id is not None:
            cand.connector_id = connector_id
        try:
            row = _candidate_to_row(cand)
            await discovered_endpoint_put(row)
            stored += 1
        except Exception:
            # Best-effort: a single failure shouldn't abort the whole batch.
            continue
    return stored


async def get_best_endpoint(action_name: str) -> dict | None:
    """Return the highest-scoring ACTIVE endpoint for an action, or None."""
    try:
        return await discovered_endpoint_get_best(action_name)
    except Exception:
        return None


async def mark_stale(endpoint_id: str, reason: str) -> None:
    """Mark a discovered endpoint as stale (so it's skipped on future replays)."""
    try:
        await discovered_endpoint_mark_stale(endpoint_id, reason)
    except Exception:
        # Marking stale is best-effort; never raise to the adapter.
        pass


async def record_replay(
    endpoint_id: str, succeeded: bool, latency_ms: int
) -> None:
    """Record the outcome of a replay attempt (success/failure + latency)."""
    try:
        await discovered_endpoint_record_replay(endpoint_id, succeeded, latency_ms)
    except Exception:
        pass


async def list_endpoints(
    action_name: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """List discovered endpoints, optionally filtered by action / status."""
    try:
        return await discovered_endpoint_list(action_name=action_name, status=status)
    except Exception:
        return []


async def get_endpoint(endpoint_id: str) -> dict | None:
    """Fetch a single endpoint by id."""
    try:
        return await discovered_endpoint_get(endpoint_id)
    except Exception:
        return None


async def delete_endpoint(endpoint_id: str) -> None:
    """Delete a discovered endpoint."""
    try:
        await discovered_endpoint_delete(endpoint_id)
    except Exception:
        pass
