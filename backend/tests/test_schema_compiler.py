"""Tests for ``app.core.contracts.schema_compiler``.

Covers:
  - ``build_contract`` returns the correct inputs/outputs for the "invoice"
    template.
  - ``build_contract`` returns the correct inputs/outputs for the "shipment"
    template.
  - ``build_contract`` returns the default contract for an unknown name.
  - ``compile_recording`` produces a TypedAction with the correct fields.
  - ``build_contract_via_llm`` returns a contract (via a stub LLM).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.contracts.schema_compiler import (
    build_contract,
    build_contract_via_llm,
    compile_recording,
)
from app.core.domain.entities import (
    CapturedStep,
    Connector,
    Recording,
    TypedAction,
)
from app.core.domain.enums import (
    ActionStatus,
    AdapterType,
    PermissionScope,
    RiskLevel,
    WorkflowCategory,
)
from app.core.domain.value_objects import FieldSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recording(name: str) -> Recording:
    return Recording(
        id="rec_test_001",
        connectorId="conn_test",
        name=name,
        steps=[
            CapturedStep(index=0, type="navigate", description="open portal",
                         url="https://example.com", networkCalls=1, durationMs=100),
            CapturedStep(index=1, type="click", description="click button",
                         selector="button.submit", networkCalls=1, durationMs=50),
        ],
        totalDurationMs=150,
        networkRequests=2,
        domMutations=4,
        screenshots=0,
    )


def _connector(category: WorkflowCategory = WorkflowCategory.finance,
               risk: RiskLevel = RiskLevel.low) -> Connector:
    return Connector(
        id="conn_test",
        name="Test Connector",
        targetApp="TestApp",
        targetDomain="test.example.com",
        workflow="testWorkflow",
        category=category,
        permission=PermissionScope.read_only,
        riskLevel=risk,
        allowedDomains=["test.example.com"],
        authMethod="api_key",
        status="active",
        credentialVaultKey="test",
        createdAt=datetime.utcnow(),
        updatedAt=datetime.utcnow(),
    )


class _StubLLM:
    """Stub LLM that returns a canned JSON contract."""

    def __init__(self, response: str):
        self._response = response

    async def complete(self, prompt: str, system: str | None = None) -> str:
        return self._response


# ---------------------------------------------------------------------------
# build_contract — invoice template
# ---------------------------------------------------------------------------

def test_build_contract_invoice_inputs():
    contract = build_contract(_recording("downloadInvoice"))
    assert len(contract.inputs) == 1
    assert contract.inputs[0].name == "invoiceId"
    assert contract.inputs[0].type == "string"
    assert contract.inputs[0].required is True


def test_build_contract_invoice_outputs():
    contract = build_contract(_recording("downloadInvoice"))
    output_names = [o.name for o in contract.outputs]
    assert "invoiceNumber" in output_names
    assert "pdfUrl" in output_names
    assert "supplierName" in output_names
    assert "amount" in output_names
    assert "status" in output_names
    # pdfUrl must be typed as 'url'.
    pdf = next(o for o in contract.outputs if o.name == "pdfUrl")
    assert pdf.type == "url"
    # amount must be typed as 'number'.
    amount = next(o for o in contract.outputs if o.name == "amount")
    assert amount.type == "number"


def test_build_contract_invoice_postconditions():
    contract = build_contract(_recording("downloadInvoice"))
    assert "pdf downloaded" in contract.postconditions
    assert "amount > 0" in contract.postconditions
    assert "status present" in contract.postconditions


def test_build_contract_invoice_preconditions_present():
    contract = build_contract(_recording("downloadInvoice"))
    # build_contract always sets connector-active + credentials-valid.
    assert "connector active" in contract.preconditions
    assert "credentials valid" in contract.preconditions


# ---------------------------------------------------------------------------
# build_contract — shipment template
# ---------------------------------------------------------------------------

def test_build_contract_shipment_inputs():
    contract = build_contract(_recording("trackShipment"))
    input_names = [i.name for i in contract.inputs]
    assert "carrier" in input_names
    assert "trackingNumber" in input_names


def test_build_contract_shipment_outputs():
    contract = build_contract(_recording("trackShipment"))
    output_names = [o.name for o in contract.outputs]
    assert "status" in output_names
    assert "eta" in output_names
    assert "currentLocation" in output_names
    assert "proofOfDeliveryUrl" in output_names
    # proofOfDeliveryUrl must be optional.
    pod = next(o for o in contract.outputs if o.name == "proofOfDeliveryUrl")
    assert pod.required is False


def test_build_contract_shipment_postconditions():
    contract = build_contract(_recording("trackShipment"))
    assert "status present" in contract.postconditions
    assert "proof of delivery available" in contract.postconditions


# ---------------------------------------------------------------------------
# build_contract — unknown name → default
# ---------------------------------------------------------------------------

def test_build_contract_unknown_name_returns_default():
    contract = build_contract(_recording("someRandomWorkflowName"))
    # Default template: one input 'id', one output 'status'.
    assert len(contract.inputs) == 1
    assert contract.inputs[0].name == "id"
    assert len(contract.outputs) >= 1
    assert any(o.name == "status" for o in contract.outputs)
    assert "status present" in contract.postconditions


def test_build_contract_case_insensitive_template_match():
    """Template matching is case-insensitive (name.lower())."""
    contract = build_contract(_recording("DOWNLOADINVOICE"))
    assert any(o.name == "pdfUrl" for o in contract.outputs)


def test_build_contract_claim_template():
    contract = build_contract(_recording("checkClaimStatus"))
    input_names = [i.name for i in contract.inputs]
    assert "patientId" in input_names
    assert "claimId" in input_names


# ---------------------------------------------------------------------------
# compile_recording
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compile_recording_produces_typed_action():
    recording = _recording("downloadInvoice")
    connector = _connector(category=WorkflowCategory.finance)
    action = await compile_recording(recording, connector, llm=None)
    assert isinstance(action, TypedAction)


@pytest.mark.asyncio
async def test_compile_recording_name_has_no_spaces():
    recording = _recording("download Invoice")  # name with space
    connector = _connector()
    action = await compile_recording(recording, connector, llm=None)
    assert " " not in action.name
    assert action.name == "downloadInvoice"


@pytest.mark.asyncio
async def test_compile_recording_finance_category_prefers_api():
    recording = _recording("downloadInvoice")
    connector = _connector(category=WorkflowCategory.finance)
    action = await compile_recording(recording, connector, llm=None)
    assert action.preferredAdapter == AdapterType.api
    assert AdapterType.api in action.executionMethods
    assert AdapterType.internal_route in action.executionMethods
    assert AdapterType.browser in action.executionMethods


@pytest.mark.asyncio
async def test_compile_recording_logistics_category_prefers_api():
    recording = _recording("trackShipment")
    connector = _connector(category=WorkflowCategory.logistics)
    action = await compile_recording(recording, connector, llm=None)
    assert action.preferredAdapter == AdapterType.api
    assert AdapterType.browser in action.executionMethods
    assert AdapterType.vision in action.executionMethods


@pytest.mark.asyncio
async def test_compile_recording_other_category_prefers_internal_route():
    recording = _recording("fillSecurityQuestionnaire")
    connector = _connector(category=WorkflowCategory.compliance)
    action = await compile_recording(recording, connector, llm=None)
    assert action.preferredAdapter == AdapterType.internal_route
    assert AdapterType.internal_route in action.executionMethods
    assert AdapterType.browser in action.executionMethods


@pytest.mark.asyncio
async def test_compile_recording_carries_contract():
    recording = _recording("downloadInvoice")
    connector = _connector()
    action = await compile_recording(recording, connector, llm=None)
    # The contract must match the invoice template.
    assert any(o.name == "pdfUrl" for o in action.contract.outputs)
    assert any(i.name == "invoiceId" for i in action.contract.inputs)


@pytest.mark.asyncio
async def test_compile_recording_signature_includes_inputs():
    recording = _recording("downloadInvoice")
    connector = _connector()
    action = await compile_recording(recording, connector, llm=None)
    assert "downloadInvoice(" in action.signature
    assert "invoiceId" in action.signature


@pytest.mark.asyncio
async def test_compile_recording_status_is_testing():
    recording = _recording("downloadInvoice")
    connector = _connector()
    action = await compile_recording(recording, connector, llm=None)
    assert action.status == ActionStatus.testing


@pytest.mark.asyncio
async def test_compile_recording_initial_version_is_0_1_0():
    recording = _recording("downloadInvoice")
    connector = _connector()
    action = await compile_recording(recording, connector, llm=None)
    assert action.version == "0.1.0"


# ---------------------------------------------------------------------------
# build_contract_via_llm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_contract_via_llm_uses_llm_response():
    recording = _recording("downloadInvoice")
    llm = _StubLLM(
        '{"inputs":[{"name":"custId","type":"string","required":true,'
        '"description":"Customer id"}],'
        '"outputs":[{"name":"total","type":"number","required":true,'
        '"description":"Total"}],'
        '"preconditions":["connector active"],'
        '"postconditions":["total > 0"]}'
    )
    contract = await build_contract_via_llm(recording, llm)
    assert len(contract.inputs) == 1
    assert contract.inputs[0].name == "custId"
    assert len(contract.outputs) == 1
    assert contract.outputs[0].name == "total"
    assert "total > 0" in contract.postconditions


@pytest.mark.asyncio
async def test_build_contract_via_llm_falls_back_on_malformed_response():
    recording = _recording("downloadInvoice")
    llm = _StubLLM("not json at all")
    contract = await build_contract_via_llm(recording, llm)
    # Must fall back to the deterministic invoice template.
    assert any(o.name == "pdfUrl" for o in contract.outputs)
    assert any(i.name == "invoiceId" for i in contract.inputs)


@pytest.mark.asyncio
async def test_build_contract_via_llm_falls_back_on_empty_inputs():
    recording = _recording("downloadInvoice")
    llm = _StubLLM('{"inputs":[],"outputs":[],"preconditions":[],"postconditions":[]}')
    contract = await build_contract_via_llm(recording, llm)
    # Empty inputs/outputs triggers the fallback to the deterministic template.
    assert len(contract.inputs) >= 1
    assert len(contract.outputs) >= 1
