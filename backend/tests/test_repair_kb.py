"""Tests for the Repair Knowledge Base flywheel (Option A — TRACK-5).

Covers:
  - Pure inference helpers: ``infer_widget_type``, ``infer_intention``,
    ``extract_target_domain``, ``compute_pattern_key``.
  - ``query_kb`` — high-confidence hit returns a ``source="knowledge_base"``
    proposal; low-confidence / no-match returns ``None``.
  - ``store_repair`` — upsert + counter preservation.
  - ``record_outcome`` — best-effort wrapper.
  - ``propose`` 3-tier ladder — KB hit short-circuits the LLM; LLM hit is
    stored in the KB; fallback path is the deterministic table.
  - ``/api/v1/monitoring/repair-kb/*`` — list / get / stats / deprecate.
  - ``/repairs/:id/resolve`` — KB outcome recording on approve / reject.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.domain.entities import (
    ActionContract, Execution, RepairProposal, TypedAction,
)
from app.core.domain.enums import (
    ActionStatus, AdapterType, Caller, ExecutionStatus, PermissionScope,
    RepairStatus, RiskLevel, WorkflowCategory,
)
from app.core.domain.value_objects import FieldSchema
from app.core.repair.knowledge_base import (
    RepairFailure,
    compute_pattern_key,
    extract_target_domain,
    infer_intention,
    infer_widget_type,
    query_kb,
    record_outcome,
    store_repair,
)
from app.core.repair.repair_proposer import propose
from app.infrastructure.prisma_repositories import (
    repair_kb_get_by_pattern, repair_kb_list, repair_kb_put,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(name: str = "downloadInvoice", version: str = "1.2.0") -> TypedAction:
    return TypedAction(
        id="act_test_kb",
        connectorId="conn_test",
        name=name,
        signature=f"{name}()",
        description="test action",
        category=WorkflowCategory.finance,
        contract=ActionContract(
            inputs=[FieldSchema("invoiceId", "string", True, "id")],
            outputs=[FieldSchema("status", "string", True, "status")],
        ),
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.api, AdapterType.browser],
        preferredAdapter=AdapterType.api,
        status=ActionStatus.published,
        version=version,
    )


def _make_failed_execution(
    error_message: str = 'selector not found: button[data-testid="download-btn"]',
    exec_id: str = "exe_test_kb_001",
) -> Execution:
    return Execution(
        id=exec_id,
        actionId="act_test_kb",
        actionName="downloadInvoice",
        caller=Caller.agent,
        inputs={"invoiceId": "INV-9999"},
        outputs=None,
        adapter=AdapterType.browser,
        fallbackChain=[AdapterType.api, AdapterType.browser],
        status=ExecutionStatus.failed,
        durationMs=900,
        startedAt=datetime.utcnow(),
        finishedAt=None,
        traces=[],
        errorMessage=error_message,
    )


class _StubLLM:
    """A stub LLM client whose ``complete`` returns a canned JSON string."""

    def __init__(self, response: str):
        self._response = response

    async def complete(self, prompt: str, system: str | None = None) -> str:
        return self._response


# ---------------------------------------------------------------------------
# infer_widget_type
# ---------------------------------------------------------------------------


def test_infer_widget_type_button():
    assert infer_widget_type('button[aria-label="Download"]') == "button"


def test_infer_widget_type_submit_input_is_button():
    """input[type='submit'] is semantically a button, not a generic input."""
    assert infer_widget_type("input[type='submit']") == "button"
    assert infer_widget_type('input[type="submit"]') == "button"


def test_infer_widget_type_link():
    assert infer_widget_type('a[data-route="tracking-detail"]') == "link"
    assert infer_widget_type("a.foo") == "link"


def test_infer_widget_type_input():
    assert infer_widget_type('input[name="email"]') == "input"


def test_infer_widget_type_select():
    assert infer_widget_type('select#country') == "select"


def test_infer_widget_type_unknown():
    assert infer_widget_type(".some-div") == "unknown"
    assert infer_widget_type("") == "unknown"


def test_infer_widget_type_falls_back_to_error_message():
    """Empty selector + error message that mentions 'button' → button."""
    assert infer_widget_type("", "could not click button") == "button"


# ---------------------------------------------------------------------------
# infer_intention
# ---------------------------------------------------------------------------


def test_infer_intention_from_action_name():
    assert infer_intention("downloadInvoice") == "download"
    assert infer_intention("trackShipment") == "track"
    assert infer_intention("checkClaimStatus") == "check"
    assert infer_intention("fillSecurityQuestionnaire") == "fill"
    assert infer_intention("exportNewCandidates") == "export"


def test_infer_intention_generic_for_unknown_action():
    assert infer_intention("doSomethingElse") == "generic"
    assert infer_intention("") == "generic"


def test_infer_intention_uses_error_message_as_fallback():
    """A generic action name paired with a 'download failed' error → download."""
    assert infer_intention("customAction", "download failed") == "download"


# ---------------------------------------------------------------------------
# extract_target_domain
# ---------------------------------------------------------------------------


def test_extract_target_domain_known_action():
    assert extract_target_domain("downloadInvoice") == "acme.com"
    assert extract_target_domain("trackShipment") == "maersk.com"
    assert extract_target_domain("checkClaimStatus") == "bluecross.com"


def test_extract_target_domain_unknown_action():
    assert extract_target_domain("someUnknownAction") == "unknown"
    assert extract_target_domain("") == "unknown"


def test_extract_target_domain_prefers_connector_when_provided():
    class _C:
        targetDomain = "supplier-portal.acme.com"

    assert extract_target_domain("downloadInvoice", connector=_C()) == "supplier-portal.acme.com"


# ---------------------------------------------------------------------------
# compute_pattern_key
# ---------------------------------------------------------------------------


def test_compute_pattern_key_format():
    assert compute_pattern_key(
        "acme.com", "button", "download", "button[data-invoice-download]",
    ) == "acme.com:button:download:button[data-invoice-download]"


def test_compute_pattern_key_is_deterministic():
    args = ("acme.com", "button", "download", "button[data-invoice-download]")
    assert compute_pattern_key(*args) == compute_pattern_key(*args)


# ---------------------------------------------------------------------------
# query_kb
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_kb_returns_none_for_empty_kb(seeded_db):
    """No KB entries → no match → returns None."""
    failure = RepairFailure(
        action_name="downloadInvoice",
        target_domain="nonexistent.com",
        failed_selector="button[data-foo]",
        widget_type="button",
        intention="download",
    )
    assert await query_kb(failure) is None


@pytest.mark.asyncio
async def test_query_kb_returns_proposal_for_high_confidence_match(seeded_db):
    """A KB entry with confidence >= 0.85 AND success_count >= 2 is returned."""
    # The seeded acme.com entry matches these criteria (conf=0.92, success=5).
    failure = RepairFailure(
        action_name="downloadInvoice",
        target_domain="acme.com",
        failed_selector="button[data-invoice-download]",
        widget_type="button",
        intention="download",
    )
    proposal = await query_kb(failure)
    assert proposal is not None
    assert proposal.source == "knowledge_base"
    assert proposal.candidateSelector == "a[aria-label='Download PDF']"
    assert proposal.patternKey == "acme.com:button:download:button[data-invoice-download]"
    assert "Cross-client repair from KB" in proposal.reason
    assert "success=5" in proposal.reason


@pytest.mark.asyncio
async def test_query_kb_returns_none_for_low_confidence_match(seeded_db):
    """A KB entry with confidence < 0.85 is NOT returned (falls through to LLM)."""
    # Insert a low-confidence entry that otherwise matches.
    await repair_kb_put({
        "patternKey": "lowconf.com:button:download:button[low]",
        "targetDomain": "lowconf.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[low]",
        "repairedSelector": "button[high]",
        "repairedLabel": "high",
        "confidence": 0.50,  # below KB_MIN_CONFIDENCE=0.85
        "source": "llm",
        "successCount": 10,
        "failureCount": 0,
        "status": "active",
    })
    failure = RepairFailure(
        action_name="downloadInvoice",
        target_domain="lowconf.com",
        failed_selector="button[low]",
        widget_type="button",
        intention="download",
    )
    assert await query_kb(failure) is None


@pytest.mark.asyncio
async def test_query_kb_returns_none_for_low_success_count(seeded_db):
    """A KB entry with success_count < 2 is NOT returned (insufficient validation)."""
    await repair_kb_put({
        "patternKey": "lowsuccess.com:button:download:button[low]",
        "targetDomain": "lowsuccess.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[low]",
        "repairedSelector": "button[high]",
        "repairedLabel": "high",
        "confidence": 0.95,  # above KB_MIN_CONFIDENCE
        "source": "llm",
        "successCount": 1,   # below KB_MIN_SUCCESS=2
        "failureCount": 0,
        "status": "active",
    })
    failure = RepairFailure(
        action_name="downloadInvoice",
        target_domain="lowsuccess.com",
        failed_selector="button[low]",
        widget_type="button",
        intention="download",
    )
    assert await query_kb(failure) is None


@pytest.mark.asyncio
async def test_query_kb_ranks_by_combined_score(seeded_db):
    """The entry with the best combined score wins, not just the highest confidence."""
    # Two entries with the same signature; one has higher confidence but a
    # lot of failures, the other has slightly lower confidence but no failures.
    await repair_kb_put({
        "patternKey": "rank.com:button:download:button[x]:high-conf-many-fails",
        "targetDomain": "rank.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[x]",
        "repairedSelector": "button[high-conf]",
        "repairedLabel": "high-conf",
        "confidence": 0.95,
        "source": "llm",
        "successCount": 5,
        "failureCount": 10,  # many failures → low combined score
        "status": "active",
    })
    await repair_kb_put({
        "patternKey": "rank.com:button:download:button[x]:lower-conf-no-fails",
        "targetDomain": "rank.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[x]",
        "repairedSelector": "button[lower-conf]",
        "repairedLabel": "lower-conf",
        "confidence": 0.90,
        "source": "llm",
        "successCount": 5,
        "failureCount": 0,   # no failures → higher combined score
        "status": "active",
    })
    failure = RepairFailure(
        action_name="downloadInvoice",
        target_domain="rank.com",
        failed_selector="button[x]",
        widget_type="button",
        intention="download",
    )
    proposal = await query_kb(failure)
    assert proposal is not None
    # The no-failures entry should win despite the lower base confidence.
    assert proposal.candidateSelector == "button[lower-conf]"


# ---------------------------------------------------------------------------
# store_repair
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_repair_inserts_new_entry(seeded_db):
    """Storing a brand-new proposal creates a KB entry with 0 counters."""
    proposal = RepairProposal(
        id="rep_test_store_1",
        actionId="act_test",
        actionVersion="1.0.0",
        failedSelector="button[old]",
        candidateSelector="button[new]",
        candidateLabel="new",
        confidence=0.88,
        reason="LLM-proposed",
        source="llm",
    )
    pattern_key = await store_repair(
        proposal, "newdomain.com", "button", "download",
    )
    assert pattern_key == "newdomain.com:button:download:button[old]"
    entry = await repair_kb_get_by_pattern(pattern_key)
    assert entry is not None
    assert entry["repairedSelector"] == "button[new]"
    assert entry["confidence"] == 0.88
    assert entry["source"] == "llm"
    assert entry["successCount"] == 0
    assert entry["failureCount"] == 0


@pytest.mark.asyncio
async def test_store_repair_preserves_existing_counters(seeded_db):
    """Re-storing a proposal does NOT clobber the learned success/failure counts."""
    # Pre-seed an entry with non-zero counters.
    await repair_kb_put({
        "patternKey": "preserve.com:button:download:button[old]",
        "targetDomain": "preserve.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[old]",
        "repairedSelector": "button[old-repair]",
        "repairedLabel": "old-repair",
        "confidence": 0.80,
        "source": "llm",
        "successCount": 7,
        "failureCount": 2,
        "autoAppliedCount": 3,
        "status": "active",
    })
    proposal = RepairProposal(
        id="rep_test_store_2",
        actionId="act_test",
        actionVersion="1.0.0",
        failedSelector="button[old]",
        candidateSelector="button[new-better]",
        candidateLabel="new-better",
        confidence=0.92,  # improved confidence on re-store
        reason="LLM-proposed v2",
        source="llm",
    )
    await store_repair(proposal, "preserve.com", "button", "download")
    entry = await repair_kb_get_by_pattern(
        "preserve.com:button:download:button[old]",
    )
    assert entry is not None
    # Selector + confidence are refreshed…
    assert entry["repairedSelector"] == "button[new-better]"
    assert entry["confidence"] == 0.92
    # …but the learned counters are preserved.
    assert entry["successCount"] == 7
    assert entry["failureCount"] == 2
    assert entry["autoAppliedCount"] == 3


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_outcome_increments_success(seeded_db):
    await repair_kb_put({
        "patternKey": "outcome.com:button:download:button[x]",
        "targetDomain": "outcome.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[x]",
        "repairedSelector": "button[y]",
        "repairedLabel": "y",
        "confidence": 0.90,
        "source": "llm",
        "successCount": 5,
        "failureCount": 1,
        "autoAppliedCount": 0,
        "status": "active",
    })
    await record_outcome(
        "outcome.com:button:download:button[x]", succeeded=True, auto_applied=True,
    )
    entry = await repair_kb_get_by_pattern(
        "outcome.com:button:download:button[x]",
    )
    assert entry is not None
    assert entry["successCount"] == 6
    assert entry["autoAppliedCount"] == 1


@pytest.mark.asyncio
async def test_record_outcome_increments_failure(seeded_db):
    await repair_kb_put({
        "patternKey": "fail.com:button:download:button[x]",
        "targetDomain": "fail.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[x]",
        "repairedSelector": "button[y]",
        "repairedLabel": "y",
        "confidence": 0.90,
        "source": "llm",
        "successCount": 5,
        "failureCount": 1,
        "status": "active",
    })
    await record_outcome("fail.com:button:download:button[x]", succeeded=False)
    entry = await repair_kb_get_by_pattern(
        "fail.com:button:download:button[x]",
    )
    assert entry is not None
    assert entry["failureCount"] == 2


@pytest.mark.asyncio
async def test_record_outcome_swallows_unknown_pattern(seeded_db):
    """Recording an outcome for a non-existent pattern is a no-op (no raise)."""
    await record_outcome("nonexistent:pattern:key", succeeded=True)


# ---------------------------------------------------------------------------
# propose — 3-tier ladder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_uses_kb_when_high_confidence_match_exists(seeded_db):
    """When the KB has a high-confidence match, propose returns it immediately.

    The KB hit short-circuits the LLM call (the LLM is provided but never
    invoked because the KB returns first).
    """
    action = _make_action(name="downloadInvoice")
    failed = _make_failed_execution(
        error_message="selector not found: button[data-invoice-download]",
    )

    class _ExplodingLLM:
        async def complete(self, *a, **kw):
            raise AssertionError("LLM should not be called when KB has a hit")

    proposal = await propose(action, failed, llm=_ExplodingLLM())
    assert proposal is not None
    assert proposal.source == "knowledge_base"
    assert proposal.candidateSelector == "a[aria-label='Download PDF']"
    assert proposal.patternKey == "acme.com:button:download:button[data-invoice-download]"


@pytest.mark.asyncio
async def test_propose_stores_llm_proposal_in_kb(seeded_db):
    """LLM proposals with confidence >= STORE_MIN_CONFIDENCE are stored in the KB.

    Uses a custom action name (not in the seeded KB) so the KB query misses
    and the LLM is invoked — exercising the store-after-LLM path.
    """
    action = _make_action(name="customActionNoKbHit")
    failed = _make_failed_execution(
        # Use a selector that doesn't match any seeded KB entry.
        error_message="selector not found: button[data-unique-new-failure]",
    )
    failed.actionName = "customActionNoKbHit"
    llm = _StubLLM(
        '{"candidateSelector":"button[llm-fix]","candidateLabel":"fix",'
        '"confidence":0.92,"reason":"stable aria"}'
    )
    proposal = await propose(action, failed, llm=llm)
    assert proposal is not None
    assert proposal.source == "llm"
    assert proposal.candidateSelector == "button[llm-fix]"
    # The proposal must have a patternKey (the KB stored it).
    assert proposal.patternKey is not None
    # Verify the entry is actually in the KB.
    entry = await repair_kb_get_by_pattern(proposal.patternKey)
    assert entry is not None
    assert entry["repairedSelector"] == "button[llm-fix]"
    assert entry["confidence"] == 0.92


@pytest.mark.asyncio
async def test_propose_does_not_store_low_confidence_llm_proposal(seeded_db):
    """LLM proposals below STORE_MIN_CONFIDENCE are NOT stored in the KB."""
    action = _make_action(name="customActionNoKbHitLow")
    failed = _make_failed_execution(
        error_message="selector not found: button[data-unique-low-conf]",
    )
    failed.actionName = "customActionNoKbHitLow"
    llm = _StubLLM(
        '{"candidateSelector":"button[low]","candidateLabel":"low",'
        '"confidence":0.55,"reason":"uncertain"}'
    )
    proposal = await propose(action, failed, llm=llm)
    assert proposal is not None
    assert proposal.source == "llm"
    # Low-confidence proposals don't get a patternKey (not stored in KB).
    assert proposal.patternKey is None


@pytest.mark.asyncio
async def test_propose_fallback_when_llm_fails(seeded_db):
    """When LLM raises / returns garbage, the deterministic fallback is used."""
    action = _make_action(name="downloadInvoice")
    failed = _make_failed_execution(
        error_message="selector not found: button[data-no-kb-match-either]",
    )
    # The KB query will return the seeded acme.com entry (matches on
    # target_domain + widget_type + intention, not failed_selector). To
    # exercise the fallback path, we need to bypass the KB hit by using
    # a custom action name that doesn't map to a seeded portal domain.
    action = _make_action(name="customActionFallback")
    failed.actionName = "customActionFallback"

    class _ExplodingLLM:
        async def complete(self, *a, **kw):
            raise RuntimeError("simulated LLM outage")

    proposal = await propose(action, failed, llm=_ExplodingLLM())
    assert proposal is not None
    assert proposal.source == "fallback"
    # The fallback for an unknown action name is the generic Submit button.
    assert proposal.candidateSelector == 'button[aria-label="Submit"]'
    # Fallback proposals are not stored in the KB.
    assert proposal.patternKey is None


@pytest.mark.asyncio
async def test_propose_returns_none_for_non_selector_error(seeded_db):
    """Non-selector errors still return None (no KB query, no LLM, no fallback)."""
    action = _make_action()
    failed = _make_failed_execution(error_message="HTTP 500: server error")
    assert await propose(action, failed, llm=None) is None


# ---------------------------------------------------------------------------
# HTTP API — /api/v1/monitoring/repair-kb/*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repair_kb_list_endpoint(seeded_db, client, auth_headers):
    """GET /monitoring/repair-kb returns all entries with successRate."""
    resp = await client.get("/api/v1/monitoring/repair-kb", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data and "total" in data
    # The seeded DB has 4 KB entries (2 from TRACK-2 + 2 new from TRACK-5).
    assert data["total"] >= 4
    for entry in data["entries"]:
        assert "successRate" in entry
        s = entry["successCount"]
        f = entry["failureCount"]
        expected = round(s / (s + f), 4) if (s + f) else 0.0
        assert entry["successRate"] == expected


@pytest.mark.asyncio
async def test_repair_kb_list_with_domain_filter(seeded_db, client, auth_headers):
    """GET /monitoring/repair-kb?targetDomain=acme.com filters by domain."""
    resp = await client.get(
        "/api/v1/monitoring/repair-kb?targetDomain=acme.com",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["entries"]
    assert len(items) >= 1
    assert all(e["targetDomain"] == "acme.com" for e in items)


@pytest.mark.asyncio
async def test_repair_kb_get_endpoint(seeded_db, client, auth_headers):
    """GET /monitoring/repair-kb/{id} returns one entry."""
    # List to grab an id.
    resp = await client.get("/api/v1/monitoring/repair-kb", headers=auth_headers)
    entry_id = resp.json()["entries"][0]["id"]

    resp = await client.get(
        f"/api/v1/monitoring/repair-kb/{entry_id}", headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == entry_id


@pytest.mark.asyncio
async def test_repair_kb_get_404_for_unknown_id(seeded_db, client, auth_headers):
    """GET /monitoring/repair-kb/{id} returns 404 for an unknown id."""
    resp = await client.get(
        "/api/v1/monitoring/repair-kb/rkb_nonexistent", headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_repair_kb_stats_endpoint(seeded_db, client, auth_headers):
    """GET /monitoring/repair-kb/stats returns the full stats payload."""
    resp = await client.get(
        "/api/v1/monitoring/repair-kb/stats", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("totalEntries", "activeEntries", "totalSuccesses",
                "totalAutoApplied", "avgConfidence", "mttrTrend", "topDomains"):
        assert key in data, f"missing key: {key}"
    # Seeded DB has ≥4 entries, ≥4 active.
    assert data["totalEntries"] >= 4
    assert data["activeEntries"] >= 1
    # MTTR trend is a 7-day list with the right shape.
    assert isinstance(data["mttrTrend"], list)
    assert len(data["mttrTrend"]) == 7
    for point in data["mttrTrend"]:
        assert "bucket" in point and "mttrMs" in point
    # Top domains is a list of {domain, successCount}.
    assert isinstance(data["topDomains"], list)
    assert len(data["topDomains"]) <= 5
    for d in data["topDomains"]:
        assert "domain" in d and "successCount" in d


@pytest.mark.asyncio
async def test_repair_kb_deprecate_endpoint(seeded_db, client, auth_headers):
    """POST /monitoring/repair-kb/{id}/deprecate marks status='deprecated'."""
    resp = await client.get("/api/v1/monitoring/repair-kb", headers=auth_headers)
    entry_id = resp.json()["entries"][0]["id"]

    resp = await client.post(
        f"/api/v1/monitoring/repair-kb/{entry_id}/deprecate",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deprecated"


@pytest.mark.asyncio
async def test_repair_kb_deprecate_excludes_from_search(seeded_db, client, auth_headers):
    """A deprecated entry is no longer returned by query_kb."""
    # The acme.com entry is normally a high-confidence hit; deprecate it.
    resp = await client.get(
        "/api/v1/monitoring/repair-kb?targetDomain=acme.com",
        headers=auth_headers,
    )
    entry_id = resp.json()["entries"][0]["id"]
    await client.post(
        f"/api/v1/monitoring/repair-kb/{entry_id}/deprecate",
        headers=auth_headers,
    )
    # Now query_kb should NOT return a hit for this signature.
    failure = RepairFailure(
        action_name="downloadInvoice",
        target_domain="acme.com",
        failed_selector="button[data-invoice-download]",
        widget_type="button",
        intention="download",
    )
    assert await query_kb(failure) is None


# ---------------------------------------------------------------------------
# resolve endpoint — KB outcome recording
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_repair_records_kb_success_for_kb_sourced(
    seeded_db, client, auth_headers,
):
    """Approving a KB-sourced repair bumps the KB entry's successCount."""
    # Use the propose flow to create a KB-sourced repair.
    action = _make_action(name="downloadInvoice")
    failed = _make_failed_execution(
        error_message="selector not found: button[data-invoice-download]",
    )
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None and proposal.source == "knowledge_base"
    pattern_key = proposal.patternKey
    # Persist the proposal so we can resolve it.
    from app.modules.monitoring.repository import put_repair
    persisted = await put_repair(proposal)

    # Snapshot the KB entry's successCount before resolution.
    before = await repair_kb_get_by_pattern(pattern_key)
    assert before is not None
    success_before = before["successCount"]

    # Resolve as approved.
    resp = await client.post(
        f"/api/v1/monitoring/repairs/{persisted.id}/resolve",
        headers=auth_headers, json={"decision": "approved"},
    )
    assert resp.status_code == 200

    # KB successCount should have incremented.
    after = await repair_kb_get_by_pattern(pattern_key)
    assert after is not None
    assert after["successCount"] == success_before + 1


@pytest.mark.asyncio
async def test_resolve_repair_stores_llm_sourced_into_kb_on_approve(
    seeded_db, client, auth_headers,
):
    """Approving an LLM-sourced repair stores it in the KB + records success."""
    # Use a custom action name (not in the seeded KB) so the KB query misses
    # and the LLM is invoked — producing an LLM-sourced proposal that the
    # resolve endpoint will then store back into the KB.
    action = _make_action(name="customActionResolveLlm")
    failed = _make_failed_execution(
        error_message="selector not found: button[data-unique-llm-then-approve]",
    )
    failed.actionName = "customActionResolveLlm"
    llm = _StubLLM(
        '{"candidateSelector":"button[llm-then-approve-fix]",'
        '"candidateLabel":"fix","confidence":0.93,"reason":"stable"}'
    )
    proposal = await propose(action, failed, llm=llm)
    assert proposal is not None and proposal.source == "llm"
    # The propose flow already stored it in the KB once (confidence ≥ 0.7).
    pattern_key = proposal.patternKey
    assert pattern_key is not None
    from app.modules.monitoring.repository import put_repair
    persisted = await put_repair(proposal)

    before = await repair_kb_get_by_pattern(pattern_key)
    success_before = before["successCount"] if before else 0

    resp = await client.post(
        f"/api/v1/monitoring/repairs/{persisted.id}/resolve",
        headers=auth_headers, json={"decision": "auto_applied"},
    )
    assert resp.status_code == 200

    after = await repair_kb_get_by_pattern(pattern_key)
    assert after is not None
    # successCount incremented AND autoAppliedCount incremented (auto_applied).
    assert after["successCount"] == success_before + 1
    assert after["autoAppliedCount"] >= 1


@pytest.mark.asyncio
async def test_resolve_repair_records_kb_failure_on_reject(
    seeded_db, client, auth_headers,
):
    """Rejecting a KB-sourced repair bumps the KB entry's failureCount."""
    action = _make_action(name="downloadInvoice")
    failed = _make_failed_execution(
        error_message="selector not found: button[data-invoice-download]",
    )
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None and proposal.source == "knowledge_base"
    pattern_key = proposal.patternKey
    from app.modules.monitoring.repository import put_repair
    persisted = await put_repair(proposal)

    before = await repair_kb_get_by_pattern(pattern_key)
    failure_before = before["failureCount"]

    resp = await client.post(
        f"/api/v1/monitoring/repairs/{persisted.id}/resolve",
        headers=auth_headers, json={"decision": "rejected"},
    )
    assert resp.status_code == 200

    after = await repair_kb_get_by_pattern(pattern_key)
    assert after is not None
    assert after["failureCount"] == failure_before + 1
