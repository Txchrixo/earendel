"""Tests for the FastAPI HTTP endpoints (via httpx.AsyncClient + ASGITransport).

Covers:
  - GET /api/v1/healthz returns {"status": "alive"}
  - GET /api/v1/readyz returns {"status": "ready", checks, counts}
  - GET /api/v1/connectors without auth returns 401
  - GET /api/v1/connectors with auth returns a list
  - GET /api/v1/actions with auth returns a list
  - POST /api/v1/executions with auth runs an action
  - GET /api/v1/monitoring/summary returns stats
  - GET /api/v1/search?q=invoice returns results
  - GET /api/v1/dashboard/activity returns events
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Public health endpoints (no auth required)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_healthz_returns_alive(client):
    r = await client.get("/api/v1/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readyz_returns_ready_with_checks_and_counts(client):
    r = await client.get("/api/v1/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "checks" in body
    assert "database" in body["checks"]
    assert "action_registry" in body["checks"]
    assert "counts" in body
    assert "connectors" in body["counts"]
    assert "actions" in body["counts"]


@pytest.mark.asyncio
async def test_readyz_after_seed_has_nonzero_counts(client):
    """After seeding, readyz should report connectors + actions > 0."""
    r = await client.get("/api/v1/readyz")
    body = r.json()
    assert body["counts"]["connectors"] >= 1
    assert body["counts"]["actions"] >= 1


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connectors_without_auth_returns_401(client):
    r = await client.get("/api/v1/connectors")
    assert r.status_code == 401
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_actions_without_auth_returns_401(client):
    r = await client.get("/api/v1/actions")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client):
    r = await client.get(
        "/api/v1/connectors",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_returns_401(client):
    """An expired JWT must be rejected by the auth middleware."""
    import jwt
    from datetime import datetime, timedelta
    from app.main import BACKEND_SECRET
    payload = {
        "uid": "usr_test",
        "email": "test@earendel.io",
        "iss": "earendel-studio",
        "aud": "earendel-api",
        "iat": int((datetime.utcnow() - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.utcnow() - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, BACKEND_SECRET, algorithm="HS256")
    r = await client.get(
        "/api/v1/connectors",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Authenticated list endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connectors_with_auth_returns_list(client, auth_headers):
    r = await client.get("/api/v1/connectors", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    # Each connector must have the expected keys.
    c = body[0]
    assert "id" in c
    assert "name" in c
    assert "category" in c


@pytest.mark.asyncio
async def test_actions_with_auth_returns_list(client, auth_headers):
    r = await client.get("/api/v1/actions", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    a = body[0]
    assert "id" in a
    assert "name" in a
    assert "contract" in a
    assert "version" in a


@pytest.mark.asyncio
async def test_actions_include_seeded_workflow_names(client, auth_headers):
    r = await client.get("/api/v1/actions", headers=auth_headers)
    names = {a["name"] for a in r.json()}
    assert "downloadInvoice" in names
    assert "trackShipment" in names
    assert "checkClaimStatus" in names


# ---------------------------------------------------------------------------
# POST /api/v1/executions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_execution_succeeds(client, auth_headers):
    """POST /api/v1/executions runs an action and returns the Execution."""
    # 1. Fetch the action list to find a runnable action id.
    r = await client.get("/api/v1/actions", headers=auth_headers)
    actions = r.json()
    invoice = next(a for a in actions if a["name"] == "downloadInvoice")
    action_id = invoice["id"]

    # 2. Run the action.
    r2 = await client.post(
        "/api/v1/executions",
        headers=auth_headers,
        json={
            "actionId": action_id,
            "inputs": {"invoiceId": "INV-TEST-001"},
            "caller": "manual",
            "riskApproved": True,
        },
    )
    assert r2.status_code == 200
    exe = r2.json()
    assert exe["actionId"] == action_id
    assert exe["actionName"] == "downloadInvoice"
    assert exe["status"] in ("success", "degraded", "human_review")
    assert "id" in exe
    assert "traces" in exe
    assert len(exe["traces"]) >= 1


@pytest.mark.asyncio
async def test_run_execution_persists_and_lists(client, auth_headers):
    """A run via POST must appear in the GET /api/v1/executions list."""
    r = await client.get("/api/v1/actions", headers=auth_headers)
    invoice = next(a for a in r.json() if a["name"] == "downloadInvoice")
    action_id = invoice["id"]

    # Run the action.
    await client.post(
        "/api/v1/executions",
        headers=auth_headers,
        json={
            "actionId": action_id,
            "inputs": {"invoiceId": "INV-LIST-TEST"},
            "caller": "manual",
            "riskApproved": True,
        },
    )

    # List executions — the new one must be present.
    r2 = await client.get("/api/v1/executions", headers=auth_headers)
    assert r2.status_code == 200
    execs = r2.json()
    assert any(e["actionName"] == "downloadInvoice" for e in execs)


@pytest.mark.asyncio
async def test_run_execution_unknown_action_raises_error(client, auth_headers):
    """An unknown actionId surfaces as an error (NotFoundError propagates).

    The app does not register a FastAPI exception handler mapping
    ``NotFoundError`` → 404, so the error propagates through the ASGI
    transport. We verify the request fails rather than silently succeeding.
    """
    from app.shared.errors import EarendelError
    with pytest.raises(EarendelError):
        await client.post(
            "/api/v1/executions",
            headers=auth_headers,
            json={"actionId": "act_does_not_exist", "inputs": {}, "caller": "manual"},
        )


# ---------------------------------------------------------------------------
# Monitoring summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monitoring_summary_returns_stats(client, auth_headers):
    r = await client.get("/api/v1/monitoring/summary", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "totalActions" in body
    assert "healthy" in body
    assert "degraded" in body
    assert "broken" in body
    assert "canaryPassRate" in body
    assert "openRepairs" in body
    assert "executions24h" in body
    assert "successRate24h" in body
    assert "mttrHours" in body
    assert body["totalActions"] >= 1


# ---------------------------------------------------------------------------
# Global search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_invoice_returns_results(client, auth_headers):
    r = await client.get(
        "/api/v1/search", params={"q": "invoice"}, headers=auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert "actions" in body
    assert "connectors" in body
    assert "executions" in body
    assert "recordings" in body
    assert "repairs" in body
    # The downloadInvoice action must be in the results.
    assert any(a["name"] == "downloadInvoice" for a in body["actions"])


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty_lists(client, auth_headers):
    r = await client.get(
        "/api/v1/search", params={"q": ""}, headers=auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["actions"] == []
    assert body["connectors"] == []


@pytest.mark.asyncio
async def test_search_shipment_matches_action(client, auth_headers):
    r = await client.get(
        "/api/v1/search", params={"q": "shipment"}, headers=auth_headers
    )
    body = r.json()
    assert any(a["name"] == "trackShipment" for a in body["actions"])


# ---------------------------------------------------------------------------
# Dashboard activity feed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_activity_returns_events(client, auth_headers):
    r = await client.get("/api/v1/dashboard/activity", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "events" in body
    assert "total" in body
    assert isinstance(body["events"], list)
    assert body["total"] >= 0
    # Each event must have the required keys.
    for e in body["events"]:
        assert "type" in e
        assert "ts" in e
        assert "title" in e
        assert "refId" in e
        assert "refType" in e


@pytest.mark.asyncio
async def test_dashboard_activity_events_are_sorted_desc(client, auth_headers):
    """Activity feed events must be sorted most-recent-first."""
    r = await client.get("/api/v1/dashboard/activity", headers=auth_headers)
    body = r.json()
    events = body["events"]
    if len(events) >= 2:
        assert events[0]["ts"] >= events[-1]["ts"]


@pytest.mark.asyncio
async def test_dashboard_activity_event_types_are_valid(client, auth_headers):
    """Every event type must be one of the known feed categories."""
    r = await client.get("/api/v1/dashboard/activity", headers=auth_headers)
    body = r.json()
    valid_types = {"execution", "repair", "recording", "version"}
    for e in body["events"]:
        assert e["type"] in valid_types
