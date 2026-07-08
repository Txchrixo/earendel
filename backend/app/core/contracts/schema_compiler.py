"""Contracts — compile a Recording into an ActionContract (LLM-assisted)."""
from __future__ import annotations

from ...core.domain.entities import ActionContract, Recording, TypedAction
from ...core.domain.enums import ActionStatus, AdapterType, PermissionScope
from ...core.domain.value_objects import FieldSchema
from ...infrastructure.llm_client import LLMClient
from ...shared.ids import new_id

# Deterministic contract templates per workflow name keyword.
_TEMPLATES = {
    "invoice": {
        "inputs": [
            FieldSchema("invoiceId", "string", True, "Supplier invoice id"),
        ],
        "outputs": [
            FieldSchema("invoiceNumber", "string", True, "Invoice number"),
            FieldSchema("pdfUrl", "url", True, "Downloaded PDF URL"),
            FieldSchema("supplierName", "string", True, "Supplier name"),
            FieldSchema("amount", "number", True, "Invoice total"),
            FieldSchema("status", "string", True, "Payment status"),
        ],
        "postconditions": ["pdf downloaded", "amount > 0", "status present"],
    },
    "shipment": {
        "inputs": [
            FieldSchema("carrier", "string", True, "Carrier code"),
            FieldSchema("trackingNumber", "string", True, "Tracking number"),
        ],
        "outputs": [
            FieldSchema("status", "string", True, "Shipment status"),
            FieldSchema("eta", "date", True, "Estimated arrival"),
            FieldSchema("currentLocation", "string", True, "Last known location"),
            FieldSchema("proofOfDeliveryUrl", "url", False, "POD PDF URL"),
        ],
        "postconditions": ["status present", "proof of delivery available"],
    },
    "claim": {
        "inputs": [
            FieldSchema("patientId", "string", True, "Patient id"),
            FieldSchema("claimId", "string", True, "Claim id"),
        ],
        "outputs": [
            FieldSchema("status", "string", True, "Claim status"),
            FieldSchema("denialReason", "string", False, "Denial reason"),
            FieldSchema("nextStep", "string", True, "Recommended next step"),
            FieldSchema("lastUpdated", "date", True, "Last update timestamp"),
        ],
        "postconditions": ["status present"],
    },
}


def _template_for(name: str) -> dict:
    n = name.lower()
    for key, tpl in _TEMPLATES.items():
        if key in n:
            return tpl
    return {
        "inputs": [FieldSchema("id", "string", True, "Primary key")],
        "outputs": [FieldSchema("status", "string", True, "Outcome status")],
        "postconditions": ["status present"],
    }


def build_contract(recording: Recording) -> ActionContract:
    """Build an ActionContract deterministically from the recording name."""
    tpl = _template_for(recording.name)
    return ActionContract(
        inputs=list(tpl["inputs"]),
        outputs=list(tpl["outputs"]),
        preconditions=["connector active", "credentials valid"],
        postconditions=list(tpl["postconditions"]),
    )


async def compile_recording(
    recording: Recording,
    connector,
    llm: LLMClient | None = None,
) -> TypedAction:
    """Compile a Recording into a registered TypedAction."""
    contract = build_contract(recording)
    name = recording.name.replace(" ", "")
    # Heuristics for adapter preference — finance prefers api, etc.
    cat = connector.category.value
    if cat == "finance":
        methods = [AdapterType.api, AdapterType.internal_route, AdapterType.browser]
        preferred = AdapterType.api
    elif cat == "logistics":
        methods = [AdapterType.api, AdapterType.browser, AdapterType.vision]
        preferred = AdapterType.api
    else:
        methods = [AdapterType.internal_route, AdapterType.browser]
        preferred = AdapterType.internal_route
    signature = f"{name}({', '.join(f'{f.name}: {f.type}' for f in contract.inputs)})"
    action = TypedAction(
        id=new_id("act"), connectorId=recording.connectorId, name=name,
        signature=signature, description=f"Compiled from recording {recording.id}",
        category=connector.category, contract=contract,
        permissions=PermissionScope.read_only, riskLevel=connector.riskLevel,
        executionMethods=methods, preferredAdapter=preferred,
        status=ActionStatus.testing, version="0.1.0",
    )
    return action
