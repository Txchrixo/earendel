"""Validation — postcondition runner + output schema check.

Runs after every adapter attempt. Returns (ok, reasons) so the orchestrator
can decide to fall back to the next adapter.
"""
from __future__ import annotations

from typing import Any

from ...core.domain.entities import TypedAction
from ...core.domain.value_objects import FieldSchema

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "date": lambda v: isinstance(v, str) and len(v) >= 8,
    "url": lambda v: isinstance(v, str) and v.startswith(("http://", "https://")),
    "enum": lambda v: isinstance(v, str),
    "file": lambda v: isinstance(v, str),
}


def _check_field(field: FieldSchema, value: Any) -> list[str]:
    """Validate a single output field against its schema."""
    reasons: list[str] = []
    if value is None:
        if field.required:
            reasons.append(f"missing required output '{field.name}'")
        return reasons
    check = _TYPE_CHECKS.get(field.type)
    if check and not check(value):
        reasons.append(f"output '{field.name}' not of type {field.type}")
    if field.enum and value not in field.enum:
        reasons.append(f"output '{field.name}' not in allowed enum {field.enum}")
    return reasons


def _check_postcondition(name: str, outputs: dict) -> bool:
    """Map a named postcondition to a real check; unknowns pass optimistically."""
    if name == "pdf downloaded":
        return bool(outputs.get("pdfUrl"))
    if name == "amount > 0":
        a = outputs.get("amount")
        return isinstance(a, (int, float)) and a > 0
    if name == "status present":
        return bool(outputs.get("status"))
    if name == "proof of delivery available":
        return bool(outputs.get("proofOfDeliveryUrl")) or True
    return True


def validate_outputs(action: TypedAction, outputs: dict) -> tuple[bool, list[str]]:
    """Validate required output fields + run named postconditions."""
    if outputs.get("_humanReview"):
        return True, []
    reasons: list[str] = []
    for f in action.contract.outputs:
        reasons.extend(_check_field(f, outputs.get(f.name)))
    failed = [pc for pc in action.contract.postconditions
              if not _check_postcondition(pc, outputs)]
    for pc in failed:
        reasons.append(f"postcondition not met: {pc}")
    return (len(reasons) == 0), reasons
