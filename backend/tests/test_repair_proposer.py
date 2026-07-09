"""Tests for ``app.core.repair.repair_proposer.propose``."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.domain.entities import (
    ActionContract,
    Execution,
    RepairProposal,
    TypedAction,
)
from app.core.domain.enums import (
    ActionStatus,
    AdapterType,
    Caller,
    ExecutionStatus,
    PermissionScope,
    RepairStatus,
    RiskLevel,
    WorkflowCategory,
)
from app.core.domain.value_objects import FieldSchema
from app.core.repair.repair_proposer import (
    propose,
    _deterministic_confidence,
    _fallback_candidate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_action(name: str = "downloadInvoice", version: str = "1.2.0") -> TypedAction:
    return TypedAction(
        id="act_test_repair",
        connectorId="conn_test",
        name=name,
        signature=f"{name}()",
        description="test action",
        category=WorkflowCategory.finance,
        contract=ActionContract(
            inputs=[FieldSchema("invoiceId", "string", True, "id")],
            outputs=[FieldSchema("status", "string", True, "status")],
            postconditions=["status present"],
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
    exec_id: str = "exe_test_failed_001",
) -> Execution:
    return Execution(
        id=exec_id,
        actionId="act_test_repair",
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


class _ExplodingLLM:
    """A stub LLM client whose ``complete`` always raises."""

    async def complete(self, prompt: str, system: str | None = None) -> str:
        raise RuntimeError("simulated LLM outage")


# ---------------------------------------------------------------------------
# Non-selector errors → None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_none_for_non_selector_error():
    action = _make_action()
    failed = _make_failed_execution(
        error_message="HTTP 500: internal server error",
    )
    proposal = await propose(action, failed, llm=None)
    assert proposal is None


@pytest.mark.asyncio
async def test_returns_none_for_empty_error_message():
    action = _make_action()
    failed = _make_failed_execution(error_message="")
    proposal = await propose(action, failed, llm=None)
    assert proposal is None


@pytest.mark.asyncio
async def test_returns_none_for_none_error_message():
    action = _make_action()
    failed = _make_failed_execution(error_message="")  # can't pass None (pydantic)
    failed.errorMessage = None
    proposal = await propose(action, failed, llm=None)
    assert proposal is None


# ---------------------------------------------------------------------------
# Selector errors → RepairProposal (no LLM → fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_proposal_for_selector_error_without_llm():
    action = _make_action()
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None
    assert isinstance(proposal, RepairProposal)


@pytest.mark.asyncio
async def test_fallback_candidate_is_used_when_no_llm():
    action = _make_action(name="downloadInvoice")
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None
    expected_selector, expected_label, _ = _fallback_candidate("downloadInvoice")
    assert proposal.candidateSelector == expected_selector
    assert proposal.candidateLabel == expected_label


@pytest.mark.asyncio
async def test_fallback_candidate_default_when_action_name_unknown():
    action = _make_action(name="someUnknownAction")
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None
    # The default fallback candidate is the generic "Submit" button.
    assert proposal.candidateSelector == 'button[aria-label="Submit"]'


@pytest.mark.asyncio
async def test_fallback_candidate_is_used_when_llm_explodes():
    """When the LLM raises, the deterministic fallback table is used."""
    action = _make_action(name="trackShipment")
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=_ExplodingLLM())
    assert proposal is not None
    expected_selector, _, _ = _fallback_candidate("trackShipment")
    assert proposal.candidateSelector == expected_selector


# ---------------------------------------------------------------------------
# Confidence range
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confidence_is_in_expected_range_without_llm():
    action = _make_action()
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None
    assert 0.75 <= proposal.confidence <= 0.96


@pytest.mark.asyncio
async def test_deterministic_confidence_function_range():
    """The raw deterministic confidence helper must stay in [0.75, 0.96]."""
    for action_id in ("act_a", "act_b", "act_c", "act_long_identifier_xyz"):
        for exec_id in ("exe_1", "exe_2", "exe_3"):
            conf = _deterministic_confidence(action_id, exec_id)
            assert 0.75 <= conf <= 0.96


@pytest.mark.asyncio
async def test_confidence_at_least_fallback_table_confidence():
    """The final confidence is max(deterministic, fallback-table)."""
    action = _make_action(name="downloadInvoice")
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=None)
    _, _, tbl_conf = _fallback_candidate("downloadInvoice")
    assert proposal.confidence >= tbl_conf


# ---------------------------------------------------------------------------
# Action id + version on proposal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proposal_has_correct_action_id_and_version():
    action = _make_action(version="1.4.2")
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None
    assert proposal.actionId == action.id
    assert proposal.actionVersion == "1.4.2"


@pytest.mark.asyncio
async def test_proposal_has_pending_status():
    action = _make_action()
    failed = _make_failed_execution()
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None
    assert proposal.status == RepairStatus.pending


@pytest.mark.asyncio
async def test_proposal_carries_failed_selector():
    action = _make_action()
    failed = _make_failed_execution(
        error_message='selector not found: button[data-testid="old-btn"]',
    )
    proposal = await propose(action, failed, llm=None)
    assert proposal is not None
    assert proposal.failedSelector == 'button[data-testid="old-btn"]'


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_proposal_is_used_when_available():
    action = _make_action()
    failed = _make_failed_execution()
    llm = _StubLLM(
        '{"candidateSelector":"a.new-selector","candidateLabel":"Download",'
        '"confidence":0.92,"reason":"more stable aria-label"}'
    )
    proposal = await propose(action, failed, llm=llm)
    assert proposal is not None
    assert proposal.candidateSelector == "a.new-selector"
    assert proposal.candidateLabel == "Download"
    assert proposal.confidence == 0.92
    assert "LLM-generated" in proposal.reason


@pytest.mark.asyncio
async def test_llm_confidence_clamped_to_valid_range():
    action = _make_action()
    failed = _make_failed_execution()
    # LLM returns an out-of-range confidence (>0.98) — must be clamped to 0.98.
    llm = _StubLLM(
        '{"candidateSelector":"a.x","candidateLabel":"x",'
        '"confidence":1.5,"reason":"r"}'
    )
    proposal = await propose(action, failed, llm=llm)
    assert proposal is not None
    assert proposal.confidence <= 0.98


@pytest.mark.asyncio
async def test_llm_returns_empty_json_falls_back_to_deterministic():
    action = _make_action(name="downloadInvoice")
    failed = _make_failed_execution()
    # LLM returns malformed JSON — proposer must fall back.
    llm = _StubLLM("this is not json at all")
    proposal = await propose(action, failed, llm=llm)
    assert proposal is not None
    expected_selector, _, _ = _fallback_candidate("downloadInvoice")
    assert proposal.candidateSelector == expected_selector
