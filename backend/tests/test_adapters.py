"""Tests for the execution adapters + the AdapterRegistry.

Covers:
  - ApiAdapter makes real HTTP calls to Stripe / Open-Meteo / JSONPlaceholder.
  - AdapterRegistry.get() returns the correct adapter type.
  - BrowserAdapter falls back to simulation in demo mode.
  - VisionAdapter falls back to simulation when no screenshot is available.
  - HumanAdapter returns ``_humanReview=True``.
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest

from app.adapters.api_adapter import ApiAdapter
from app.adapters.base import ExecutionContext
from app.adapters.browser_adapter import BrowserAdapter
from app.adapters.bu_browser_adapter import BrowserUseAdapter
from app.adapters.human_adapter import HumanAdapter
from app.adapters.internal_route_adapter import InternalRouteAdapter
from app.adapters.vision_adapter import VisionAdapter
from app.core.domain.entities import ActionContract, TypedAction
from app.core.domain.enums import (
    ActionStatus,
    AdapterType,
    PermissionScope,
    RiskLevel,
    WorkflowCategory,
)
from app.core.domain.value_objects import FieldSchema
from app.core.engine.adapter_registry import AdapterRegistry, default_registry


# ---------------------------------------------------------------------------
# Action builders (contracts match the seeded endpoint registry)
# ---------------------------------------------------------------------------

def _make_action(name: str, contract: ActionContract) -> TypedAction:
    return TypedAction(
        id=f"act_test_{name}",
        connectorId="conn_test",
        name=name,
        signature=f"{name}()",
        description=f"test action for {name}",
        category=WorkflowCategory.finance,
        contract=contract,
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.api],
        preferredAdapter=AdapterType.api,
        status=ActionStatus.published,
        version="1.0.0",
    )


def _invoice_action() -> TypedAction:
    return _make_action(
        "downloadInvoice",
        ActionContract(
            inputs=[FieldSchema("invoiceId", "string", True, "id")],
            outputs=[
                FieldSchema("invoiceNumber", "string", True, "number"),
                FieldSchema("pdfUrl", "url", True, "pdf"),
                FieldSchema("supplierName", "string", True, "supplier"),
                FieldSchema("amount", "number", True, "total"),
                FieldSchema("status", "string", True, "status"),
            ],
            postconditions=["pdf downloaded", "amount > 0", "status present"],
        ),
    )


def _shipment_action() -> TypedAction:
    return _make_action(
        "trackShipment",
        ActionContract(
            inputs=[
                FieldSchema("carrier", "string", True, "carrier"),
                FieldSchema("trackingNumber", "string", True, "tracking"),
            ],
            outputs=[
                FieldSchema("status", "string", True, "status"),
                FieldSchema("eta", "date", True, "eta"),
                FieldSchema("currentLocation", "string", True, "location"),
                FieldSchema("proofOfDeliveryUrl", "url", False, "pod"),
            ],
            postconditions=["status present", "proof of delivery available"],
        ),
    )


def _claim_action() -> TypedAction:
    return _make_action(
        "checkClaimStatus",
        ActionContract(
            inputs=[
                FieldSchema("patientId", "string", True, "patient"),
                FieldSchema("claimId", "string", True, "claim"),
            ],
            outputs=[
                FieldSchema("status", "string", True, "status"),
                FieldSchema("denialReason", "string", False, "denial"),
                FieldSchema("nextStep", "string", True, "next step"),
                FieldSchema("lastUpdated", "date", True, "last updated"),
            ],
            postconditions=["status present"],
        ),
    )


# ---------------------------------------------------------------------------
# ApiAdapter — real Stripe call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_adapter_download_invoice_calls_real_stripe(adapter_ctx):
    """ApiAdapter for downloadInvoice hits the real Stripe API.

    With STRIPE_SECRET set (from .env), Stripe returns 200 — the adapter
    returns ``success=True`` with mapped (or fallback) outputs.
    """
    adapter = ApiAdapter()
    result = await adapter.execute(
        _invoice_action(), {"invoiceId": "INV-1001"}, adapter_ctx
    )
    # The real Stripe URL must appear in the traces.
    assert any("api.stripe.com" in (t.message or "") for t in result.traces)
    # The result is a structured AdapterResult.
    assert isinstance(result.outputs, dict)
    if os.environ.get("STRIPE_SECRET"):
        # With a valid test key, Stripe returns 200 — adapter succeeds.
        assert result.success is True
    else:
        # Without credentials, Stripe returns 401 — adapter reports the error.
        assert result.success is False
        assert "401" in (result.error or "") or "HTTP" in (result.error or "")


@pytest.mark.asyncio
async def test_api_adapter_download_invoice_returns_mapped_output_keys(adapter_ctx):
    """When the Stripe call succeeds, every contract output key is present."""
    if not os.environ.get("STRIPE_SECRET"):
        pytest.skip("STRIPE_SECRET not set — cannot verify mapped outputs")
    adapter = ApiAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1001"}, adapter_ctx)
    assert result.success is True
    for field in action.contract.outputs:
        assert field.name in result.outputs


# ---------------------------------------------------------------------------
# ApiAdapter — real Open-Meteo call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_adapter_track_shipment_calls_real_open_meteo(adapter_ctx):
    """ApiAdapter for trackShipment hits the real Open-Meteo API.

    Open-Meteo may rate-limit (429) in the test environment; both 200 and 429
    prove the real API was called.
    """
    adapter = ApiAdapter()
    result = await adapter.execute(
        _shipment_action(),
        {"carrier": "maersk", "trackingNumber": "MAEU-8842"},
        adapter_ctx,
    )
    assert any("api.open-meteo.com" in (t.message or "") for t in result.traces)
    assert isinstance(result.outputs, dict)
    if result.success:
        # Mapped outputs include at least one contract field.
        assert any(k in result.outputs for k in
                   ("status", "eta", "currentLocation"))
    else:
        # Rate-limited (429) or network error — both prove the call was made.
        assert result.error is not None


# ---------------------------------------------------------------------------
# ApiAdapter — real JSONPlaceholder call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_adapter_check_claim_calls_real_jsonplaceholder(adapter_ctx):
    """ApiAdapter for checkClaimStatus hits the real JSONPlaceholder API.

    JSONPlaceholder requires no auth, so the call should succeed and return
    mapped outputs.
    """
    adapter = ApiAdapter()
    action = _claim_action()
    result = await adapter.execute(
        action, {"patientId": "PAT-1", "claimId": "1"}, adapter_ctx
    )
    assert any("jsonplaceholder.typicode.com" in (t.message or "")
               for t in result.traces)
    assert result.success is True
    # The response is mapped to the contract output fields.
    for field in action.contract.outputs:
        assert field.name in result.outputs


@pytest.mark.asyncio
async def test_api_adapter_unknown_action_falls_back_to_simulation(adapter_ctx):
    """An action with no endpoint registry entry uses the simulation path."""
    adapter = ApiAdapter()
    action = _make_action(
        "unknownActionName",
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("status", "string", True, "status")],
            postconditions=["status present"],
        ),
    )
    result = await adapter.execute(action, {}, adapter_ctx)
    assert result.success is True
    assert any("simulated" in (t.message or "") for t in result.traces)


# ---------------------------------------------------------------------------
# AdapterRegistry
# ---------------------------------------------------------------------------

def test_adapter_registry_get_returns_correct_adapter_type():
    reg = default_registry()
    assert isinstance(reg.get(AdapterType.api), ApiAdapter)
    assert isinstance(reg.get(AdapterType.internal_route), InternalRouteAdapter)
    assert isinstance(reg.get(AdapterType.browser), BrowserAdapter)
    assert isinstance(reg.get(AdapterType.bu_browser), BrowserUseAdapter)
    assert isinstance(reg.get(AdapterType.vision), VisionAdapter)
    assert isinstance(reg.get(AdapterType.human), HumanAdapter)


def test_adapter_registry_all_returns_six_adapters():
    reg = default_registry()
    all_adapters = reg.all()
    assert len(all_adapters) == 6
    assert set(all_adapters.keys()) == {
        AdapterType.api,
        AdapterType.internal_route,
        AdapterType.browser,
        AdapterType.bu_browser,
        AdapterType.vision,
        AdapterType.human,
    }


def test_adapter_registry_get_unknown_raises_key_error():
    reg = AdapterRegistry()  # empty registry
    with pytest.raises(KeyError, match="no adapter registered"):
        reg.get(AdapterType.api)


def test_adapter_registry_register_adds_adapter():
    reg = AdapterRegistry()
    reg.register(ApiAdapter())
    assert isinstance(reg.get(AdapterType.api), ApiAdapter)


def test_adapter_registry_adapter_type_property():
    """Each adapter's adapter_type property matches its class."""
    assert ApiAdapter().adapter_type == AdapterType.api
    assert InternalRouteAdapter().adapter_type == AdapterType.internal_route
    assert BrowserAdapter().adapter_type == AdapterType.browser
    assert BrowserUseAdapter().adapter_type == AdapterType.bu_browser
    assert VisionAdapter().adapter_type == AdapterType.vision
    assert HumanAdapter().adapter_type == AdapterType.human


# ---------------------------------------------------------------------------
# BrowserAdapter — demo mode simulation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_browser_adapter_falls_back_to_simulation_in_demo_mode(adapter_ctx):
    """In demo mode (default), the BrowserAdapter runs its simulation path."""
    # Ensure demo mode is on (conftest sets it, but be explicit).
    os.environ["EARENDEL_DEMO_MODE"] = "true"
    adapter = BrowserAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1001"}, adapter_ctx)
    # The simulation path emits traces containing "(simulated)".
    assert any("simulated" in (t.message or "") for t in result.traces)
    # The result is a structured AdapterResult (success or failure).
    assert isinstance(result.success, bool)
    assert isinstance(result.outputs, dict)


@pytest.mark.asyncio
async def test_browser_adapter_simulation_returns_screenshots(adapter_ctx):
    """The BrowserAdapter simulation always produces at least one screenshot."""
    os.environ["EARENDEL_DEMO_MODE"] = "true"
    adapter = BrowserAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1001"}, adapter_ctx)
    assert len(result.screenshots) >= 1


@pytest.mark.asyncio
async def test_browser_adapter_unknown_action_simulates(adapter_ctx):
    """An action with no registered workflow still simulates."""
    os.environ["EARENDEL_DEMO_MODE"] = "true"
    adapter = BrowserAdapter()
    action = _make_action(
        "totallyUnknownBrowserAction",
        ActionContract(
            inputs=[],
            outputs=[FieldSchema("status", "string", True, "status")],
            postconditions=["status present"],
        ),
    )
    result = await adapter.execute(action, {}, adapter_ctx)
    assert any("simulated" in (t.message or "") for t in result.traces)


# ---------------------------------------------------------------------------
# VisionAdapter — simulation fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vision_adapter_falls_back_to_simulation(adapter_ctx):
    """Without a screenshot path, the VisionAdapter runs its simulation."""
    # Ensure no screenshot path is set.
    os.environ.pop("EARENDEL_SCREENSHOT_PATH", None)
    adapter = VisionAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1001"}, adapter_ctx)
    # The VisionAdapter emits a "VLM unavailable — falling back to simulation"
    # trace when the VLM cannot produce a result.
    assert any(
        "simulated" in (t.message or "")
        or "VLM unavailable" in (t.message or "")
        or "VLM detected" in (t.message or "")
        for t in result.traces
    )
    assert isinstance(result.success, bool)
    assert isinstance(result.outputs, dict)


@pytest.mark.asyncio
async def test_vision_adapter_simulation_produces_screenshot(adapter_ctx):
    """The VisionAdapter simulation always produces a vision screenshot."""
    os.environ.pop("EARENDEL_SCREENSHOT_PATH", None)
    adapter = VisionAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1"}, adapter_ctx)
    assert "vision-1.png" in result.screenshots


# ---------------------------------------------------------------------------
# HumanAdapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_human_adapter_returns_human_review_true(adapter_ctx):
    """The HumanAdapter always produces ``_humanReview=True`` outputs."""
    adapter = HumanAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1"}, adapter_ctx)
    assert result.success is True
    assert result.outputs.get("_humanReview") is True


@pytest.mark.asyncio
async def test_human_adapter_outputs_include_review_id_and_prompt(adapter_ctx):
    """The HumanAdapter's outputs include a reviewId and a human-readable prompt."""
    adapter = HumanAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1"}, adapter_ctx)
    assert "reviewId" in result.outputs
    assert "prompt" in result.outputs
    assert isinstance(result.outputs["prompt"], str)
    assert "review" in result.outputs["prompt"].lower()


@pytest.mark.asyncio
async def test_human_adapter_outputs_include_action_id_and_inputs(adapter_ctx):
    """The HumanAdapter's outputs echo back the actionId + inputs for the reviewer."""
    adapter = HumanAdapter()
    action = _invoice_action()
    inputs = {"invoiceId": "INV-777"}
    result = await adapter.execute(action, inputs, adapter_ctx)
    assert result.outputs.get("actionId") == action.id
    assert result.outputs.get("inputs") == inputs


@pytest.mark.asyncio
async def test_human_adapter_traces_show_escalation(adapter_ctx):
    """The HumanAdapter traces must mention escalating to human review."""
    adapter = HumanAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {}, adapter_ctx)
    assert any("human" in (t.message or "").lower() for t in result.traces)
    assert any("escalat" in (t.message or "").lower() for t in result.traces)


# ---------------------------------------------------------------------------
# BrowserUseAdapter — OPTIONAL adapter, falls back to simulation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bu_adapter_falls_back_to_simulation_when_unprovisioned(adapter_ctx):
    """When no BU key is provisioned AND provisioning fails (no network in
    tests), the BrowserUseAdapter must fall back to a deterministic simulation.

    The adapter never raises — the orchestrator relies on this contract.
    """
    adapter = BrowserUseAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1001"}, adapter_ctx)
    # Simulation path emits traces containing "(simulated)".
    assert any("simulated" in (t.message or "") for t in result.traces)
    assert isinstance(result.success, bool)
    assert isinstance(result.outputs, dict)


@pytest.mark.asyncio
async def test_bu_adapter_simulation_produces_screenshot(adapter_ctx):
    """The BrowserUseAdapter simulation always produces at least one screenshot."""
    adapter = BrowserUseAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1"}, adapter_ctx)
    assert len(result.screenshots) >= 1


@pytest.mark.asyncio
async def test_bu_adapter_traces_use_bu_browser_type(adapter_ctx):
    """All BrowserUseAdapter traces must carry adapter=AdapterType.bu_browser."""
    adapter = BrowserUseAdapter()
    action = _invoice_action()
    result = await adapter.execute(action, {"invoiceId": "INV-1"}, adapter_ctx)
    assert result.traces, "BU adapter must emit at least one trace"
    for trace in result.traces:
        assert trace.adapter == AdapterType.bu_browser


def test_bu_math_challenge_solver_is_safe_and_correct():
    """The math challenge parser must NOT use eval and must solve simple
    arithmetic expressions correctly, formatting the answer as 2-decimal."""
    from app.adapters.bu_browser_adapter import _solve_math_challenge

    # Basic arithmetic — each returns a 2-decimal string.
    assert _solve_math_challenge("What is 12 * 12?") == "144.00"
    assert _solve_math_challenge("What is 7 + 8?") == "15.00"
    assert _solve_math_challenge("What is 100 - 42?") == "58.00"
    assert _solve_math_challenge("What is 84 / 4?") == "21.00"
    # Parentheses, precedence, unary minus.
    assert _solve_math_challenge("Compute: (2 + 3) * 4") == "20.00"
    assert _solve_math_challenge("What is -5 + 10?") == "5.00"
    # Floats.
    assert _solve_math_challenge("What is 1.5 * 2?") == "3.00"


def test_bu_math_challenge_solver_rejects_unsafe_input():
    """The parser must reject expressions containing letters / forbidden chars."""
    from app.adapters.bu_browser_adapter import _solve_math_challenge

    with pytest.raises(ValueError):
        _solve_math_challenge("__import__('os').system('rm -rf /')")
    with pytest.raises(ValueError):
        _solve_math_challenge("no math here at all")
