"""Tests for the network discovery system (Option B — TRACK-4).

Covers:
  - ``analyze_har`` — scoring, clustering, filtering noise, field-mapping
    inference, body-template inference, cookie env-var inference.
  - ``analyze_har`` — graceful degradation on malformed/empty HAR.
  - ``InternalRouteAdapter`` — fallback ladder (discovered -> hardcoded ->
    simulation) with trace propagation.
  - ``/api/v1/discovery/*`` — HTTP endpoints (stats, analyze, list,
    get-one, mark-stale).
"""
from __future__ import annotations

import json

import pytest

from app.adapters.internal_route_adapter import InternalRouteAdapter
from app.core.discovery.har_analyzer import (
    DiscoveredEndpointCandidate,
    _build_body_template,
    _infer_cookie_env_var,
    _infer_field_mapping,
    _normalize_path,
    analyze_har,
)
from app.core.discovery.demo_har import _synthesize_demo_har
from app.core.domain.enums import AdapterType


# ---------------------------------------------------------------------------
# _normalize_path
# ---------------------------------------------------------------------------


def test_normalize_path_replaces_uuids():
    assert _normalize_path(
        "https://x.com/api/invoices/550e8400-e29b-41d4-a716-446655440000"
    ) == "/api/invoices/{id}"


def test_normalize_path_replaces_numeric_ids():
    assert _normalize_path("https://x.com/v2/users/12345") == "/v2/users/{id}"


def test_normalize_path_replaces_alpha_dash_digit_ids():
    assert _normalize_path(
        "https://x.com/api/invoices/INV-123/download"
    ) == "/api/invoices/{id}/download"


def test_normalize_path_leaves_named_segments_alone():
    assert _normalize_path("https://x.com/api/invoices/download") == "/api/invoices/download"


def test_normalize_path_handles_bad_url():
    assert _normalize_path("") == "/"


# ---------------------------------------------------------------------------
# _infer_cookie_env_var
# ---------------------------------------------------------------------------


def test_infer_cookie_env_var_simple_domain():
    assert _infer_cookie_env_var("https://acme.com/api/x") == "ACME_SESSION_COOKIE"


def test_infer_cookie_env_var_subdomain():
    assert _infer_cookie_env_var("https://supplier-portal.acme.com/x") == "ACME_SESSION_COOKIE"


def test_infer_cookie_env_var_multi_tld():
    assert _infer_cookie_env_var("https://portal.bluecross.co.uk/x") == "BLUECROSS_SESSION_COOKIE"


def test_infer_cookie_env_var_empty_url():
    assert _infer_cookie_env_var("") == "SESSION_COOKIE"


# ---------------------------------------------------------------------------
# _infer_field_mapping
# ---------------------------------------------------------------------------


def test_field_mapping_exact_case_insensitive():
    m = _infer_field_mapping(["status", "total"], ["status", "amount"])
    assert m == {"status": "status", "amount": "total"}


def test_field_mapping_snake_to_camel():
    m = _infer_field_mapping(
        ["invoice_number", "supplier_name"], ["invoiceNumber", "supplierName"]
    )
    assert m == {"invoiceNumber": "invoice_number", "supplierName": "supplier_name"}


def test_field_mapping_synonyms():
    m = _infer_field_mapping(["download_url", "total"], ["pdfUrl", "amount"])
    assert m == {"pdfUrl": "download_url", "amount": "total"}


def test_field_mapping_empty_inputs():
    assert _infer_field_mapping([], ["x"]) == {}
    assert _infer_field_mapping(["x"], []) == {}


def test_field_mapping_no_match_returns_partial():
    m = _infer_field_mapping(["unrelated_key"], ["invoiceNumber"])
    assert m == {}


# ---------------------------------------------------------------------------
# _build_body_template
# ---------------------------------------------------------------------------


def test_build_body_template_value_match():
    pd = {"mimeType": "application/json", "text": json.dumps({"id": "INV-1001"})}
    out = _build_body_template(pd, {"invoiceId": "INV-1001"})
    assert out == {"id": "{invoiceId}"}


def test_build_body_template_key_match():
    pd = {"mimeType": "application/json",
          "text": json.dumps({"invoiceId": "WHATEVER"})}
    out = _build_body_template(pd, {"invoiceId": "<sample>"})
    assert out == {"invoiceId": "{invoiceId}"}


def test_build_body_template_handles_form_params():
    pd = {"params": [{"name": "k", "value": "v"}]}
    out = _build_body_template(pd, {"k": "v"})
    assert out == {"k": "{k}"}


def test_build_body_template_handles_empty():
    assert _build_body_template(None, {}) == {}
    assert _build_body_template({}, {}) == {}
    assert _build_body_template({"text": "not-json"}, {}) == {}


# ---------------------------------------------------------------------------
# analyze_har — scoring + clustering
# ---------------------------------------------------------------------------


def test_analyze_har_returns_empty_for_none():
    assert analyze_har(None, "downloadInvoice") == []


def test_analyze_har_returns_empty_for_malformed():
    assert analyze_har({}, "downloadInvoice") == []
    assert analyze_har({"log": {}}, "downloadInvoice") == []
    assert analyze_har({"log": {"entries": "not-a-list"}}, "downloadInvoice") == []
    assert analyze_har({"log": {"entries": []}}, "downloadInvoice") == []


def test_analyze_har_filters_static_assets_and_analytics():
    har = {
        "log": {
            "entries": [
                # Noise: static asset.
                {"request": {"method": "GET", "url": "https://x.com/main.js"},
                 "response": {"status": 200, "content": {"mimeType": "application/javascript"}}},
                # Noise: analytics.
                {"request": {"method": "POST", "url": "https://www.google-analytics.com/collect"},
                 "response": {"status": 200, "content": {"mimeType": "image/gif"}}},
                # Business: POST returning JSON with action keywords.
                {"request": {"method": "POST",
                             "url": "https://x.com/api/invoices/INV-1/download",
                             "postData": {"mimeType": "application/json",
                                          "text": json.dumps({"invoiceId": "INV-1"})}},
                 "response": {"status": 200,
                              "content": {"mimeType": "application/json",
                                          "text": json.dumps({"invoice_number": "INV-1"})}}},
            ]
        }
    }
    cands = analyze_har(har, "downloadInvoice")
    assert len(cands) == 1
    assert cands[0].method == "POST"
    assert cands[0].url == "https://x.com/api/invoices/INV-1/download"
    assert cands[0].url_pattern == "*/api/invoices/{id}/download"
    # POST (+0.3) + JSON (+0.2) + keyword "invoice" (+0.2) + 200 (+0.15)
    # + /api/ (+0.1) + body (+0.05) = 1.0
    assert cands[0].business_score == 1.0


def test_analyze_har_returns_top_3():
    har = {
        "log": {
            "entries": [
                *[{"request": {"method": "POST",
                               "url": f"https://x.com/api/invoices/INV-{i}/download",
                               "postData": {"text": json.dumps({"invoiceId": f"INV-{i}"})}},
                   "response": {"status": 200,
                                "content": {"mimeType": "application/json",
                                            "text": json.dumps({"invoice_number": f"INV-{i}"})}}}
                  for i in range(5)],
                # A second distinct cluster.
                {"request": {"method": "GET", "url": "https://x.com/api/health"},
                 "response": {"status": 200, "content": {"mimeType": "application/json",
                                                         "text": "{}"}}},
            ]
        }
    }
    cands = analyze_har(har, "downloadInvoice")
    # All POSTs cluster together (normalized to /api/invoices/{id}/download),
    # the GET is a separate cluster. So 2 candidates.
    assert len(cands) == 2
    assert cands[0].business_score >= cands[1].business_score
    # The POST cluster has size 5.
    assert cands[0].cluster_size == 5


def test_analyze_har_demo_hars_all_produce_candidates():
    """Each of the 6 seeded actions' demo HAR produces at least one candidate
    with a high business score and a non-empty body_template + field_mapping.
    """
    for action in ("downloadInvoice", "trackShipment", "checkClaimStatus",
                   "downloadMarketplaceReport", "exportNewCandidates",
                   "fillSecurityQuestionnaire"):
        har = _synthesize_demo_har(action)
        cands = analyze_har(har, action)
        assert cands, f"no candidates for {action}"
        top = cands[0]
        assert top.business_score >= 0.5, f"{action} score too low: {top.business_score}"
        assert top.body_template, f"{action} body_template empty"
        assert top.field_mapping, f"{action} field_mapping empty"
        assert top.cookie_env_var.endswith("_SESSION_COOKIE"), \
            f"{action} cookie_env_var wrong: {top.cookie_env_var}"


# ---------------------------------------------------------------------------
# InternalRouteAdapter — fallback ladder + trace propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_internal_route_adapter_falls_back_to_simulation_when_no_cookie(
    adapter_ctx, seeded_db,
):
    """With an active discovered endpoint in the DB but no cookie env var,
    the adapter must fall through to simulation and the traces must show
    both the discovered-path attempt and the simulation traces."""
    # Pre-seed a discovered endpoint for an action that doesn't have a
    # hardcoded route (so we test the discovered -> simulation fallthrough
    # directly, skipping the hardcoded layer).
    from app.core.discovery.endpoint_store import store_discovered_endpoints
    from app.core.discovery.har_analyzer import DiscoveredEndpointCandidate
    cand = DiscoveredEndpointCandidate(
        action_name="trackShipment",
        method="POST",
        url="https://api.maersk.com/internal/v1/shipments/{id}/track",
        url_pattern="*/internal/v1/shipments/{id}/track",
        business_score=0.95,
        cluster_size=3,
        body_template={"carrier": "{carrier}", "trackingNumber": "{trackingNumber}"},
        cookie_env_var="MAERSK_SESSION_COOKIE",
        field_mapping={"status": "shipment_status", "eta": "eta"},
    )
    stored = await store_discovered_endpoints([cand], "trackShipment", None)
    assert stored == 1

    from app.core.domain.entities import ActionContract, TypedAction
    from app.core.domain.enums import ActionStatus, PermissionScope, RiskLevel, WorkflowCategory
    from app.core.domain.value_objects import FieldSchema
    action = TypedAction(
        id="act_test_track", connectorId="conn_test", name="trackShipment",
        signature="trackShipment()", description="t", category=WorkflowCategory.logistics,
        contract=ActionContract(
            inputs=[FieldSchema("carrier", "string", True, ""),
                    FieldSchema("trackingNumber", "string", True, "")],
            outputs=[FieldSchema("status", "string", True, ""),
                     FieldSchema("eta", "date", True, "")],
            postconditions=["status present"],
        ),
        permissions=PermissionScope.read_only, riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.internal_route],
        preferredAdapter=AdapterType.internal_route,
        status=ActionStatus.published, version="1.0.0",
    )
    adapter = InternalRouteAdapter()
    result = await adapter.execute(
        action, {"carrier": "maersk", "trackingNumber": "MAEU-1"}, adapter_ctx,
    )
    # Simulation succeeds.
    assert result.success is True
    assert "status" in result.outputs
    # Traces show both the discovered-path attempt and the simulation.
    messages = [t.message for t in result.traces]
    assert any("from HAR capture" in m for m in messages), messages
    assert any("no session cookie" in m for m in messages), messages
    assert any("simulated" in m for m in messages), messages


# ---------------------------------------------------------------------------
# Discovery HTTP API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discovery_stats_endpoint_returns_well_formed_payload(
    client, auth_headers, seeded_db,
):
    """GET /discovery/stats returns a well-formed payload with all keys.

    The seeded DB has 2 DiscoveredEndpoint rows (from the TRACK-2 seed), so
    the counts are non-zero — we assert the shape, not the exact counts.
    """
    resp = await client.get("/api/v1/discovery/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # All expected keys present.
    for key in ("totalEndpoints", "activeEndpoints", "staleEndpoints",
                "totalReplays", "successRate", "avgLatencyMs"):
        assert key in data, f"missing key: {key}"
    # Seeded DB has at least the 2 seeded endpoints.
    assert data["totalEndpoints"] >= 2
    assert data["activeEndpoints"] >= 1
    # Success rate is a float in [0, 1].
    assert 0.0 <= data["successRate"] <= 1.0
    # avg latency is a non-negative int.
    assert isinstance(data["avgLatencyMs"], int)
    assert data["avgLatencyMs"] >= 0


@pytest.mark.asyncio
async def test_discovery_analyze_endpoint_creates_endpoint(
    client, auth_headers, seeded_db,
):
    """POST /discovery/analyze stores the candidate and returns it."""
    har = _synthesize_demo_har("downloadInvoice")
    resp = await client.post(
        "/api/v1/discovery/analyze",
        headers=auth_headers,
        json={"har": har, "actionName": "downloadInvoice"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert len(data["created"]) == 1
    ep = data["created"][0]
    assert ep["actionName"] == "downloadInvoice"
    assert ep["method"] == "POST"
    assert ep["status"] == "active"
    assert "supplier-portal.acme.com" in ep["url"]
    assert ep["cookieEnvVar"] == "ACME_SESSION_COOKIE"
    # bodyTemplate is a JSON string with the {invoiceId} placeholder.
    assert "{invoiceId}" in ep["bodyTemplate"]


@pytest.mark.asyncio
async def test_discovery_list_and_get_and_mark_stale(
    client, auth_headers, seeded_db,
):
    """GET /discovery/endpoints, GET /{id}, POST /{id}/mark-stale."""
    # Seed one via /analyze.
    har = _synthesize_demo_har("trackShipment")
    resp = await client.post(
        "/api/v1/discovery/analyze",
        headers=auth_headers,
        json={"har": har, "actionName": "trackShipment"},
    )
    assert resp.status_code == 200
    created = resp.json()["created"][0]
    epid = created["id"]

    # List.
    resp = await client.get("/api/v1/discovery/endpoints", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["endpoints"]
    assert any(e["id"] == epid for e in items)

    # List with action filter.
    resp = await client.get(
        "/api/v1/discovery/endpoints?actionName=trackShipment",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert all(e["actionName"] == "trackShipment"
               for e in resp.json()["endpoints"])

    # Get one.
    resp = await client.get(
        f"/api/v1/discovery/endpoints/{epid}", headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == epid

    # Mark stale.
    resp = await client.post(
        f"/api/v1/discovery/endpoints/{epid}/mark-stale",
        headers=auth_headers, json={"reason": "test stale"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "stale"
    assert resp.json()["staleReason"] == "test stale"

    # Stats reflect the stale.
    resp = await client.get("/api/v1/discovery/stats", headers=auth_headers)
    data = resp.json()
    assert data["staleEndpoints"] >= 1


@pytest.mark.asyncio
async def test_discovery_get_unknown_returns_404(client, auth_headers, seeded_db):
    resp = await client.get(
        "/api/v1/discovery/endpoints/dep_does_not_exist", headers=auth_headers,
    )
    assert resp.status_code == 404
