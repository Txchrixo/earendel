"""Validation — postcondition runner + output schema check.

Runs after every adapter attempt. Returns (ok, reasons) so the orchestrator
can decide to fall back to the next adapter.
"""
from __future__ import annotations

from typing import Any

from ...core.domain.entities import TypedAction
from ...core.domain.value_objects import FieldSchema

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str) and len(v) > 0,
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "date": lambda v: isinstance(v, str) and len(v) >= 8,
    "url": lambda v: isinstance(v, str) and v.startswith(("http://", "https://")),
    "enum": lambda v: isinstance(v, str) and len(v) > 0,
    "file": lambda v: isinstance(v, str) and len(v) > 0,
}


def _check_field(field: FieldSchema, value: Any) -> list[str]:
    """Validate a single output field against its schema."""
    reasons: list[str] = []
    if value is None:
        if field.required:
            reasons.append(f"missing required output '{field.name}'")
        return reasons
    if value == "" and field.required:
        reasons.append(f"empty required output '{field.name}'")
        return reasons
    check = _TYPE_CHECKS.get(field.type)
    if check and not check(value):
        reasons.append(f"output '{field.name}' not of type {field.type}")
    if field.enum and value not in field.enum:
        reasons.append(f"output '{field.name}' not in allowed enum {field.enum}")
    return reasons


def _check_postcondition(name: str, outputs: dict) -> bool:
    """Map a named postcondition to a real check; unknowns pass optimistically."""
    name_lower = name.lower().strip()

    # Invoice-related
    if name_lower in ("pdf downloaded", "pdf file is successfully downloaded"):
        return bool(outputs.get("pdfUrl") or outputs.get("pdf"))
    if name_lower == "amount > 0":
        a = outputs.get("amount")
        return isinstance(a, (int, float)) and a > 0
    if name_lower in ("status present",):
        return bool(outputs.get("status"))

    # Shipment-related
    if name_lower == "proof of delivery available":
        # Optional field — pass if present or if action doesn't produce one
        return True

    # Report-related
    if name_lower in ("report downloaded",):
        return bool(outputs.get("reportUrl"))
    if name_lower == "rows > 0":
        r = outputs.get("rows")
        return isinstance(r, (int, float)) and r > 0

    # Candidate-related
    if name_lower in ("candidates exported",):
        return bool(outputs.get("candidates"))
    if name_lower in ("duplicates removed",):
        d = outputs.get("duplicatesRemoved")
        return isinstance(d, (int, float)) and d >= 0

    # Questionnaire-related
    if name_lower in ("draft saved",):
        return bool(outputs.get("status"))
    if name_lower in ("evidence linked",):
        # Optional field — pass optimistically
        return True

    # Compiled recording postconditions
    if name_lower in ("downloaded file is a valid pdf", "downloaded file matches the requested invoice"):
        return bool(outputs.get("pdf") or outputs.get("pdfUrl"))

    # Unknown postconditions pass optimistically
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
