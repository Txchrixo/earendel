"""Seed — realistic, idempotent demo data for the Earendel studio.

Creates 3 connectors, 2 recordings, 3 published typed actions, ~6 executions,
2 repair proposals, and a canary test per action. Re-running is a no-op once
connectors exist in the Prisma DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .core.domain.entities import (
    ActionVersion, CanaryAssertion, CanaryTest, Execution, RepairProposal,
    TraceEvent, TypedAction,
)
from .core.domain.enums import (
    ActionStatus, AdapterType, Caller, ExecutionStatus, PermissionScope,
    PublishTarget, RepairStatus, RiskLevel, WorkflowCategory,
)
from .core.domain.value_objects import FieldSchema
from .core.domain.entities import ActionContract
from .infrastructure.prisma_repositories import (
    discovered_endpoint_put, repair_kb_put, repair_put,
)
from .modules.connectors.service import create_connector, fetch_all as fetch_connectors
from .modules.recordings.repository import put_recording
from .modules.recordings.simulator import simulate_recording
from .modules.executions.repository import put_execution
from .shared.ids import new_id


def _contract_invoice() -> ActionContract:
    """Contract for downloadInvoice."""
    return ActionContract(
        inputs=[FieldSchema("invoiceId", "string", True, "Supplier invoice id")],
        outputs=[
            FieldSchema("invoiceNumber", "string", True, "Invoice number"),
            FieldSchema("pdfUrl", "url", True, "Downloaded PDF URL"),
            FieldSchema("supplierName", "string", True, "Supplier name"),
            FieldSchema("amount", "number", True, "Invoice total"),
            FieldSchema("status", "string", True, "Payment status",
                        enum=("paid", "pending", "overdue")),
        ],
        preconditions=["connector active", "credentials valid"],
        postconditions=["pdf downloaded", "amount > 0", "status present"],
    )


def _contract_shipment() -> ActionContract:
    """Contract for trackShipment."""
    return ActionContract(
        inputs=[
            FieldSchema("carrier", "string", True, "Carrier code"),
            FieldSchema("trackingNumber", "string", True, "Tracking number"),
        ],
        outputs=[
            FieldSchema("status", "string", True, "Shipment status"),
            FieldSchema("eta", "date", True, "Estimated arrival"),
            FieldSchema("currentLocation", "string", True, "Last known location"),
            FieldSchema("proofOfDeliveryUrl", "url", False, "POD PDF URL"),
        ],
        preconditions=["connector active"],
        postconditions=["status present", "proof of delivery available"],
    )


def _contract_claim() -> ActionContract:
    """Contract for checkClaimStatus."""
    return ActionContract(
        inputs=[
            FieldSchema("patientId", "string", True, "Patient id"),
            FieldSchema("claimId", "string", True, "Claim id"),
        ],
        outputs=[
            FieldSchema("status", "string", True, "Claim status"),
            FieldSchema("denialReason", "string", False, "Denial reason"),
            FieldSchema("nextStep", "string", True, "Recommended next step"),
            FieldSchema("lastUpdated", "date", True, "Last update timestamp"),
        ],
        preconditions=["connector active"],
        postconditions=["status present"],
    )


def _contract_marketplace_report() -> ActionContract:
    """Contract for downloadMarketplaceReport (ecommerce)."""
    return ActionContract(
        inputs=[
            FieldSchema("marketplace", "string", True, "Marketplace code",
                        enum=("amazon", "ebay", "shopify", "walmart")),
            FieldSchema("reportType", "string", True, "Report type",
                        enum=("settlement", "returns", "inventory", "sales")),
            FieldSchema("dateRange", "string", True, "ISO date range YYYY-MM-DD..YYYY-MM-DD"),
        ],
        outputs=[
            FieldSchema("reportUrl", "url", True, "Downloaded report URL"),
            FieldSchema("rows", "number", True, "Row count"),
            FieldSchema("periodStart", "date", True, "Period start"),
            FieldSchema("periodEnd", "date", True, "Period end"),
            FieldSchema("currency", "string", True, "Settlement currency"),
        ],
        preconditions=["connector active", "seller account authorised"],
        postconditions=["report downloaded", "rows > 0"],
    )


def _contract_candidates() -> ActionContract:
    """Contract for exportNewCandidates (HR)."""
    return ActionContract(
        inputs=[
            FieldSchema("jobId", "string", True, "Internal job id"),
            FieldSchema("source", "string", False, "Portal source",
                        enum=("linkedin", "indeed", "glassdoor", "all")),
        ],
        outputs=[
            FieldSchema("candidates", "file", True, "Candidate export (CSV)"),
            FieldSchema("count", "number", True, "Candidate count"),
            FieldSchema("duplicatesRemoved", "number", True, "Dedup count"),
            FieldSchema("topMatchScore", "number", False, "Best match score 0..1"),
        ],
        preconditions=["connector active", "job published"],
        postconditions=["candidates exported", "duplicates removed"],
    )


def _contract_questionnaire() -> ActionContract:
    """Contract for fillSecurityQuestionnaire (compliance)."""
    return ActionContract(
        inputs=[
            FieldSchema("portalUrl", "url", True, "Vendor portal URL"),
            FieldSchema("knowledgeBaseId", "string", True, "Company KB reference"),
        ],
        outputs=[
            FieldSchema("filledFields", "number", True, "Auto-filled answers"),
            FieldSchema("needsReview", "number", True, "Answers needing human review"),
            FieldSchema("evidenceRefs", "file", False, "Evidence bundle (ZIP)"),
            FieldSchema("status", "string", True, "Draft status",
                        enum=("draft", "submitted", "in_review")),
        ],
        preconditions=["connector active", "KB indexed"],
        postconditions=["draft saved", "evidence linked"],
    )


def _make_canary(action_id: str, name: str, passed: bool, pass_rate: float
                 ) -> CanaryTest:
    """Build a deterministic canary test for an action."""
    return CanaryTest(
        id=new_id("can"), actionId=action_id, name=name,
        schedule="*/15 * * * *", lastRun=datetime.utcnow() - timedelta(minutes=12),
        lastStatus="passed" if passed else "failed", passRate=pass_rate,
        assertions=[
            CanaryAssertion(name="postconditions_met", passed=passed),
            CanaryAssertion(name="latency_under_2s", passed=True),
            CanaryAssertion(name="no_human_review", passed=passed),
        ],
    )


def _make_version(version: str, adapter: AdapterType, changelog: str,
                  success_rate: float = 0.97) -> ActionVersion:
    """Build an ActionVersion entry."""
    return ActionVersion(
        version=version, releasedAt=datetime.utcnow() - timedelta(days=2),
        changelog=changelog, adapter=adapter, successRate=success_rate,
        status="stable",
    )


def _snapshot_contract(contract: ActionContract, drop_outputs: int = 0,
                       extra_outputs: list | None = None) -> ActionContract:
    """Build a contract snapshot for a version (simulating evolution).

    drop_outputs: remove that many output fields (older versions had fewer).
    extra_outputs: additional FieldSchema to add (newer versions added fields).
    """
    outs = list(contract.outputs)
    if drop_outputs > 0:
        outs = outs[:-drop_outputs] if drop_outputs < len(outs) else []
    if extra_outputs:
        outs = outs + list(extra_outputs)
    return ActionContract(
        inputs=list(contract.inputs),
        outputs=outs,
        preconditions=list(contract.preconditions),
        postconditions=list(contract.postconditions),
    )


async def _build_action(
    connector, name: str, signature: str, description: str,
    contract: ActionContract, methods: list[AdapterType],
    preferred: AdapterType, status: ActionStatus = ActionStatus.published,
) -> TypedAction:
    """Construct a published TypedAction with versions + canary.

    Each version carries a contractSnapshot so the version-diff view can show
    how the inputs/outputs evolved (v1.0.0 had fewer outputs, v1.1.0 added one).
    """
    action_id = new_id("act")
    # v1.0.0: initial compile — fewer outputs (drop the last 1-2 fields).
    v1_contract = _snapshot_contract(contract, drop_outputs=min(2, len(contract.outputs)))
    # v1.1.0: added retry — added one output field back.
    v1_1_contract = _snapshot_contract(contract, drop_outputs=min(1, len(contract.outputs)))
    # v1.2.0: current contract.
    return TypedAction(
        id=action_id, connectorId=connector.id, name=name,
        signature=signature, description=description, category=connector.category,
        contract=contract, permissions=PermissionScope.read_only,
        riskLevel=connector.riskLevel, executionMethods=methods,
        preferredAdapter=preferred, status=status, version="1.2.0",
        versions=[
            ActionVersion(
                version="1.0.0", releasedAt=datetime.utcnow() - timedelta(days=14),
                changelog="initial compile", adapter=preferred, successRate=0.91,
                status="stable", contractSnapshot=v1_contract,
            ),
            ActionVersion(
                version="1.1.0", releasedAt=datetime.utcnow() - timedelta(days=7),
                changelog="added retry on timeout", adapter=preferred, successRate=0.95,
                status="stable", contractSnapshot=v1_1_contract,
            ),
            ActionVersion(
                version="1.2.0", releasedAt=datetime.utcnow(),
                changelog="selector hardened after repair", adapter=preferred,
                successRate=0.98, status="latest", contractSnapshot=contract,
            ),
        ],
        testsPassed=8, testsTotal=8,
        canary=[_make_canary(action_id, f"{name} canary", True, 0.96)],
        publishedAs=[PublishTarget.mcp, PublishTarget.rest, PublishTarget.sdk],
        mcpToolName=f"earendel_{name.lower()}",
    )


async def _persist_execution(
    action: TypedAction, inputs: dict, outputs: dict | None,
    adapter: AdapterType, status: ExecutionStatus, error: str | None,
    traces: list[TraceEvent], risk_approved: bool = True, caller: Caller = Caller.agent,
) -> Execution:
    """Persist a seeded Execution with rich traces."""
    started = datetime.utcnow() - timedelta(minutes=15)
    exe = Execution(
        id=new_id("exe"), actionId=action.id, actionName=action.name,
        caller=caller, inputs=inputs, outputs=outputs, adapter=adapter,
        fallbackChain=action.executionMethods, status=status, durationMs=900,
        startedAt=started, finishedAt=started + timedelta(seconds=2),
        traces=traces, screenshots=[], postconditionsMet=status == ExecutionStatus.success,
        errorMessage=error, riskApproved=risk_approved,
    )
    return await put_execution(exe)


async def run(action_registry) -> dict[str, str]:
    """Seed the Prisma DB; idempotent. Returns seeded action ids."""
    existing = await fetch_connectors()
    if existing:
        # Already seeded — return the existing action ids for the frontend.
        return {a.name: a.id for a in action_registry.list()}

    # 1. Connectors — mapped to real public APIs
    stripe = await create_connector(
        "Stripe API", "Stripe", "api.stripe.com",
        "downloadInvoice", WorkflowCategory.finance, PermissionScope.read_only,
        RiskLevel.low, ["api.stripe.com"], "api_key")
    openmeteo = await create_connector(
        "Open-Meteo API", "Open-Meteo", "api.open-meteo.com",
        "trackShipment", WorkflowCategory.logistics, PermissionScope.read_only,
        RiskLevel.low, ["api.open-meteo.com"], "api_key")
    jsonplaceholder = await create_connector(
        "JSONPlaceholder API", "JSONPlaceholder", "jsonplaceholder.typicode.com",
        "checkClaimStatus", WorkflowCategory.healthcare, PermissionScope.read_only,
        RiskLevel.medium, ["jsonplaceholder.typicode.com"], "api_key")
    coingecko = await create_connector(
        "CoinGecko API", "CoinGecko", "api.coingecko.com",
        "downloadMarketplaceReport", WorkflowCategory.ecommerce,
        PermissionScope.read_only, RiskLevel.low,
        ["api.coingecko.com"], "api_key")
    pokeapi = await create_connector(
        "PokeAPI", "PokeAPI", "pokeapi.co",
        "exportNewCandidates", WorkflowCategory.hr, PermissionScope.read_write,
        RiskLevel.medium, ["pokeapi.co"], "api_key")
    hackernews = await create_connector(
        "Hacker News API", "Hacker News", "hacker-news.firebaseio.com",
        "fillSecurityQuestionnaire", WorkflowCategory.compliance,
        PermissionScope.submit, RiskLevel.high, ["hacker-news.firebaseio.com"], "api_key")

    # 2. Recordings (for connectors 1 and 2)
    rec_stripe = simulate_recording(stripe.id, "downloadInvoice")
    rec_stripe.status = "compiled"
    await put_recording(rec_stripe)
    rec_meteo = simulate_recording(openmeteo.id, "trackShipment")
    rec_meteo.status = "compiled"
    await put_recording(rec_meteo)

    # 3. Published TypedActions
    invoice_action = await _build_action(
        stripe, "downloadInvoice", "downloadInvoice(invoiceId: string)",
        "Download an invoice via the Stripe API (test mode).",
        _contract_invoice(),
        [AdapterType.api, AdapterType.internal_route, AdapterType.browser],
        AdapterType.api)
    shipment_action = await _build_action(
        openmeteo, "trackShipment", "trackShipment(carrier: string, trackingNumber: string)",
        "Track shipment conditions via the Open-Meteo weather API.",
        _contract_shipment(),
        [AdapterType.api, AdapterType.browser, AdapterType.vision],
        AdapterType.api)
    claim_action = await _build_action(
        jsonplaceholder, "checkClaimStatus",
        "checkClaimStatus(patientId: string, claimId: string)",
        "Check claim status via the JSONPlaceholder API.",
        _contract_claim(),
        [AdapterType.internal_route, AdapterType.browser],
        AdapterType.internal_route)
    marketplace_action = await _build_action(
        coingecko, "downloadMarketplaceReport",
        "downloadMarketplaceReport(marketplace: string, reportType: string, dateRange: string)",
        "Download a market report via the CoinGecko API.",
        _contract_marketplace_report(),
        # bu_browser is listed here to exercise the OPTIONAL adapter in the
        # fallback chain — it activates only if api + internal_route + browser
        # all fail. This is the one seeded action that opts into BU.
        [AdapterType.api, AdapterType.internal_route, AdapterType.browser,
         AdapterType.bu_browser, AdapterType.vision],
        AdapterType.api)
    candidates_action = await _build_action(
        pokeapi, "exportNewCandidates",
        "exportNewCandidates(jobId: string, source?: string)",
        "Export candidate data via the PokeAPI.",
        _contract_candidates(),
        [AdapterType.api, AdapterType.browser],
        AdapterType.api)
    questionnaire_action = await _build_action(
        hackernews, "fillSecurityQuestionnaire",
        "fillSecurityQuestionnaire(portalUrl: string, knowledgeBaseId: string)",
        "Pre-fill a questionnaire via the Hacker News API. "
        "Submits a draft for human review — never auto-submits.",
        _contract_questionnaire(),
        [AdapterType.browser, AdapterType.vision, AdapterType.human],
        AdapterType.browser,
        status=ActionStatus.testing)
    for a in (invoice_action, shipment_action, claim_action,
              marketplace_action, candidates_action, questionnaire_action):
        await action_registry.put(a)

    # 4. Executions — mix of statuses with rich traces.
    await _persist_execution(
        invoice_action, {"invoiceId": "INV-1001"},
        {"invoiceNumber": "INV-1001", "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
         "supplierName": "Acme Supplies GmbH", "amount": 4280.50, "status": "paid"},
        AdapterType.api, ExecutionStatus.success, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="GET /api/v1/downloadInvoice", step="http.request", durationMs=40),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="200 OK", step="http.response", durationMs=80)],
        caller=Caller.agent)
    await _persist_execution(
        invoice_action, {"invoiceId": "INV-2042"},
        {"invoiceNumber": "INV-2042", "pdfUrl": "https://files.acme.com/invoices/INV-2042.pdf",
         "supplierName": "Acme Supplies GmbH", "amount": 1150.00, "status": "pending"},
        AdapterType.api, ExecutionStatus.success, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="GET /api/v1/downloadInvoice", step="http.request", durationMs=44),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="200 OK", step="http.response", durationMs=88)],
        caller=Caller.schedule)
    await _persist_execution(
        shipment_action, {"carrier": "maersk", "trackingNumber": "MAEU-8842"},
        {"status": "in_transit", "eta": "2025-02-14", "currentLocation": "Rotterdam, NL",
         "proofOfDeliveryUrl": None},
        AdapterType.api, ExecutionStatus.success, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="GET /api/v1/trackShipment", step="http.request", durationMs=46),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="200 OK", step="http.response", durationMs=72)],
        caller=Caller.agent)
    await _persist_execution(
        shipment_action, {"carrier": "maersk", "trackingNumber": "MAEU-9999"},
        None, AdapterType.browser, ExecutionStatus.degraded,
        "selector not found: button[data-testid='download-btn']",
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="warn",
                    message="api adapter timed out; falling back", step="fallback"),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.browser, level="error",
                    message='selector not found: button[data-testid="download-btn"]',
                    step="click", durationMs=380),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.vision, level="info",
                    message="OmniParser detected 14 elements", step="parse", durationMs=900),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.vision, level="info",
                    message="grounded target via icon embedding", step="ground")],
        caller=Caller.agent)
    await _persist_execution(
        claim_action, {"patientId": "PAT-501", "claimId": "CLM-7782"},
        {"status": "denied", "denialReason": "missing prior authorization",
         "nextStep": "resubmit with PA document", "lastUpdated": "2025-01-22"},
        AdapterType.internal_route, ExecutionStatus.success, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.internal_route, level="info",
                    message="discovered endpoint /internal/v2/checkClaimStatus", step="discover"),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.internal_route, level="info",
                    message="200 OK", step="http.response", durationMs=140)],
        caller=Caller.agent)
    await _persist_execution(
        claim_action, {"patientId": "PAT-601", "claimId": "CLM-9999"},
        {"_humanReview": True,
         "prompt": "Manual review requested for action 'checkClaimStatus'."},
        AdapterType.human, ExecutionStatus.human_review, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.internal_route, level="warn",
                    message="internal route failed; falling back", step="fallback"),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.browser, level="error",
                    message="selector not found", step="click", durationMs=380),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.human, level="warn",
                    message="escalating to human review", step="escalate")],
        caller=Caller.manual, risk_approved=False)

    # 4b. Executions for the new verticals.
    await _persist_execution(
        marketplace_action,
        {"marketplace": "amazon", "reportType": "settlement", "dateRange": "2025-01-01..2025-01-31"},
        {"reportUrl": "https://sellercentral.amazon.com/reports/settlement-2025-01.csv",
         "rows": 1284, "periodStart": "2025-01-01", "periodEnd": "2025-01-31", "currency": "EUR"},
        AdapterType.api, ExecutionStatus.success, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="GET /reports/2021-09-30/reports?reportType=SETTLEMENT",
                    step="http.request", durationMs=120),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="report document ready", step="poll", durationMs=2100)],
        caller=Caller.schedule)
    await _persist_execution(
        marketplace_action,
        {"marketplace": "amazon", "reportType": "returns", "dateRange": "2025-01-01..2025-01-31"},
        {"reportUrl": "https://sellercentral.amazon.com/reports/returns-2025-01.csv",
         "rows": 47, "periodStart": "2025-01-01", "periodEnd": "2025-01-31", "currency": "EUR"},
        AdapterType.internal_route, ExecutionStatus.success, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="warn",
                    message="official API 404; falling back", step="fallback"),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.internal_route, level="info",
                    message="discovered /internal/returns/download", step="discover", durationMs=180),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.internal_route, level="info",
                    message="200 OK", step="http.response", durationMs=220)],
        caller=Caller.agent)
    await _persist_execution(
        candidates_action,
        {"jobId": "JOB-204", "source": "linkedin"},
        {"candidates": "exports/candidates-JOB-204.csv", "count": 38,
         "duplicatesRemoved": 11, "topMatchScore": 0.92},
        AdapterType.api, ExecutionStatus.success, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="GET /v1/partner/v1/jobs/204/candidates", step="http.request", durationMs=95),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.api, level="info",
                    message="LLM dedup: 11 candidates merged", step="dedup", durationMs=480)],
        caller=Caller.agent)
    await _persist_execution(
        questionnaire_action,
        {"portalUrl": "https://app.drata.com/vendor/secure", "knowledgeBaseId": "kb-soc2-v3"},
        {"filledFields": 84, "needsReview": 12,
         "evidenceRefs": "evidence/drata-soc2-bundle.zip", "status": "draft"},
        AdapterType.browser, ExecutionStatus.human_review, None,
        [TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.browser, level="info",
                    message="goto vendor security questionnaire", step="navigate", durationMs=1400),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.browser, level="info",
                    message="RAG retrieved 84 answers from kb-soc2-v3", step="rag", durationMs=720),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.browser, level="warn",
                    message="12 answers below confidence threshold — flagged for review", step="flag"),
         TraceEvent(ts=datetime.utcnow(), adapter=AdapterType.human, level="warn",
                    message="draft saved; awaiting compliance lead approval", step="escalate")],
        caller=Caller.agent, risk_approved=False)

    # 5. Repair proposals (one pending, one auto_applied).
    rep1 = RepairProposal(
        id=new_id("rep"), actionId=shipment_action.id, actionVersion="1.2.0",
        failedSelector='button[data-testid="download-btn"]',
        candidateSelector='a[data-route="tracking-detail"]',
        candidateLabel='a[data-route="tracking-detail"]',
        confidence=0.88,
        reason="semantically equivalent stable selector after selector drift",
        status=RepairStatus.pending, detectedAt=datetime.utcnow() - timedelta(hours=4),
        source="llm")
    rep2 = RepairProposal(
        id=new_id("rep"), actionId=invoice_action.id, actionVersion="1.1.0",
        failedSelector='button[data-testid="download-btn"]',
        candidateSelector='button[aria-label="Download invoice"]',
        candidateLabel='button[aria-label="Download invoice"]',
        confidence=0.91,
        reason="repaired after first canary failure; auto-applied by healer",
        status=RepairStatus.auto_applied, detectedAt=datetime.utcnow() - timedelta(days=1),
        source="llm")
    await repair_put(rep1.model_dump(mode="json"))
    await repair_put(rep2.model_dump(mode="json"))

    # 6. DiscoveredEndpoint seeds (Network Discovery — Option B).
    # Two real-looking internal endpoints harvested from HAR captures,
    # one for downloadInvoice (finance) and one for checkClaimStatus (healthcare).
    await discovered_endpoint_put({
        "id": new_id("dep"),
        "actionName": "downloadInvoice",
        "connectorId": stripe.id,
        "method": "POST",
        "url": "https://supplier-portal.acme.com/internal/v2/invoices/download",
        "urlPattern": "*/internal/v2/invoices/download",
        "bodyTemplate": '{"invoiceId": "{invoiceId}"}',
        "headersTemplate": '{"X-XSRF-TOKEN": "{xsrf}"}',
        "cookieEnvVar": "ACME_SESSION_COOKIE",
        "fieldMapping": '{"invoiceNumber": "invoice_number", "pdfUrl": "download_url", '
                        '"supplierName": "supplier_name", "amount": "total", '
                        '"status": "payment_status"}',
        "responseShape": '{"invoice_number": "string", "download_url": "url", '
                         '"supplier_name": "string", "total": "number", '
                         '"payment_status": "string"}',
        "businessScore": 0.92,
        "clusterSize": 14,
        "status": "active",
        "timesReplayed": 18, "timesSucceeded": 17, "timesFailed": 1,
        "avgLatencyMs": 142,
        "discoveredFrom": "har",
        "lastReplayedAt": datetime.utcnow() - timedelta(hours=2),
    })
    await discovered_endpoint_put({
        "id": new_id("dep"),
        "actionName": "checkClaimStatus",
        "connectorId": jsonplaceholder.id,
        "method": "POST",
        "url": "https://provider.bluecross.com/internal/v2/claims/check",
        "urlPattern": "*/internal/v2/claims/check",
        "bodyTemplate": '{"patientId": "{patientId}", "claimId": "{claimId}"}',
        "headersTemplate": '{"X-XSRF-TOKEN": "{xsrf}"}',
        "cookieEnvVar": "BLUECROSS_SESSION_COOKIE",
        "fieldMapping": '{"status": "claim_status", "denialReason": "denial_reason", '
                        '"nextStep": "next_step", "lastUpdated": "last_updated"}',
        "responseShape": '{"claim_status": "string", "denial_reason": "string?", '
                         '"next_step": "string", "last_updated": "date"}',
        "businessScore": 0.81,
        "clusterSize": 9,
        "status": "active",
        "timesReplayed": 11, "timesSucceeded": 9, "timesFailed": 2,
        "avgLatencyMs": 218,
        "discoveredFrom": "har",
        "lastReplayedAt": datetime.utcnow() - timedelta(days=1),
    })

    # 7. RepairKnowledge seeds (Repair Flywheel — Option A).
    # Two cross-client repair patterns — one LLM-sourced, one manual — both
    # with enough success_count to be auto-applied by future runs.
    await repair_kb_put({
        "id": new_id("rkb"),
        "patternKey": "finance:button:download:download-btn:download-invoice",
        "targetDomain": "finance",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": 'button[data-testid="download-btn"]',
        "repairedSelector": 'button[aria-label="Download invoice"]',
        "repairedLabel": "Download invoice",
        "confidence": 0.91,
        "source": "llm",
        "successCount": 7,
        "failureCount": 1,
        "autoAppliedCount": 3,
        "status": "active",
        "lastUsedAt": datetime.utcnow() - timedelta(days=1),
    })
    await repair_kb_put({
        "id": new_id("rkb"),
        "patternKey": "logistics:button:track:download-btn:tracking-detail",
        "targetDomain": "logistics",
        "widgetType": "link",
        "intention": "navigate",
        "failedSelector": 'button[data-testid="download-btn"]',
        "repairedSelector": 'a[data-route="tracking-detail"]',
        "repairedLabel": "Tracking detail",
        "confidence": 0.86,
        "source": "manual",
        "successCount": 4,
        "failureCount": 0,
        "autoAppliedCount": 1,
        "status": "active",
        "lastUsedAt": datetime.utcnow() - timedelta(hours=8),
    })
    # Two more cross-client seeds using real portal domains (the spec's
    # canonical examples) so the KB has hits out-of-the-box for the
    # downloadInvoice (acme.com) and checkClaimStatus (bluecross.com)
    # workflows. These pattern keys follow the compute_pattern_key format
    # ``{target_domain}:{widget_type}:{intention}:{failed_selector}``.
    await repair_kb_put({
        "id": new_id("rkb"),
        "patternKey": "acme.com:button:download:button[data-invoice-download]",
        "targetDomain": "acme.com",
        "widgetType": "button",
        "intention": "download",
        "failedSelector": "button[data-invoice-download]",
        "repairedSelector": "a[aria-label='Download PDF']",
        "repairedLabel": "Download PDF",
        "confidence": 0.92,
        "source": "llm",
        "successCount": 5,
        "failureCount": 1,
        "autoAppliedCount": 3,
        "status": "active",
        "lastUsedAt": datetime.utcnow() - timedelta(hours=3),
    })
    await repair_kb_put({
        "id": new_id("rkb"),
        "patternKey": "bluecross.com:button:check:button[aria-label='Search claims']",
        "targetDomain": "bluecross.com",
        "widgetType": "button",
        "intention": "check",
        "failedSelector": "button[aria-label='Search claims']",
        "repairedSelector": "button#claim-search-btn",
        "repairedLabel": "Search claims",
        "confidence": 0.88,
        "source": "llm",
        "successCount": 3,
        "failureCount": 0,
        "autoAppliedCount": 1,
        "status": "active",
        "lastUsedAt": datetime.utcnow() - timedelta(hours=12),
    })

    return {
        invoice_action.name: invoice_action.id,
        shipment_action.name: shipment_action.id,
        claim_action.name: claim_action.id,
        marketplace_action.name: marketplace_action.id,
        candidates_action.name: candidates_action.id,
        questionnaire_action.name: questionnaire_action.id,
    }
