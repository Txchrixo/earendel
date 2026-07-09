"""Contracts — compile a Recording into an ActionContract (LLM-assisted)."""
from __future__ import annotations

import json
import re

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
    """Build an ActionContract deterministically from the recording name (fallback)."""
    tpl = _template_for(recording.name)
    return ActionContract(
        inputs=list(tpl["inputs"]),
        outputs=list(tpl["outputs"]),
        preconditions=["connector active", "credentials valid"],
        postconditions=list(tpl["postconditions"]),
    )


async def build_contract_via_llm(
    recording: Recording, llm: LLMClient
) -> ActionContract:
    """Use the LLM to infer an ActionContract from the captured steps.

    Sends the step descriptions + selectors + values and asks for a JSON
    contract (inputs/outputs/preconditions/postconditions). Falls back to the
    deterministic template if parsing fails.
    """
    steps_summary = "\n".join(
        f"- step {s.index + 1}: {s.type} — {s.description}"
        + (f" [selector={s.selector}]" if s.selector else "")
        + (f" [value={s.value}]" if s.value else "")
        for s in recording.steps
    )
    prompt = (
        "You are Earendel's workflow compiler. Given a recorded human workflow, "
        "infer the typed action contract. Return ONLY valid JSON (no prose, no "
        "markdown fences) with this exact shape:\n"
        '{"inputs":[{"name","type","required","description"}],'
        '"outputs":[{"name","type","required","description"}],'
        '"preconditions":["..."],"postconditions":["..."]}\n\n'
        f"Workflow name: {recording.name}\n"
        f"Captured steps ({len(recording.steps)}):\n{steps_summary}\n\n"
        "Types must be one of: string, number, boolean, date, url, enum, file.\n"
        "Inputs are fields the agent must supply; outputs are what the workflow produces."
    )
    system = (
        "You are a precise JSON-only API. Never include prose or markdown. "
        "Infer business-action contracts from recorded UI workflows."
    )
    try:
        raw = await llm.complete(prompt=prompt, system=system)
        data = _parse_json_lenient(raw)
        inputs = [
            FieldSchema(
                name=f["name"],
                type=f.get("type", "string"),
                required=f.get("required", False),
                description=f.get("description", ""),
            )
            for f in data.get("inputs", [])
        ]
        outputs = [
            FieldSchema(
                name=f["name"],
                type=f.get("type", "string"),
                required=f.get("required", False),
                description=f.get("description", ""),
            )
            for f in data.get("outputs", [])
        ]
        if not inputs or not outputs:
            raise ValueError("LLM returned empty inputs or outputs")
        return ActionContract(
            inputs=inputs,
            outputs=outputs,
            preconditions=data.get("preconditions", ["connector active"]),
            postconditions=data.get("postconditions", ["status present"]),
        )
    except Exception:
        # Fall back to the deterministic template.
        return build_contract(recording)


def _parse_json_lenient(raw: str) -> dict:
    """Parse JSON from an LLM response, tolerating markdown fences + prose."""
    # Strip markdown code fences if present.
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = cleaned.replace("```", "")
    # Find the first { ... } block.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object found")
    return json.loads(cleaned[start : end + 1])


async def compile_recording(
    recording: Recording,
    connector,
    llm: LLMClient | None = None,
) -> TypedAction:
    """Compile a Recording into a registered TypedAction.

    Uses the LLM to infer the contract when an LLMClient is provided;
    otherwise falls back to the deterministic template.
    """
    if llm is not None:
        contract = await build_contract_via_llm(recording, llm)
    else:
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
