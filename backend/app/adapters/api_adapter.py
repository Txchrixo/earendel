"""Adapter 1 — Official REST API.

Simulates a successful call to the target system's public API. Fast,
high-reliability, the preferred path when the contract allows it.
"""
from __future__ import annotations

from datetime import datetime

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from .base import AdapterResult, ExecutionContext, ExecutionAdapter


def _ok_outputs(action: TypedAction, inputs: dict) -> dict:
    """Produce deterministic outputs matching the action's contract."""
    out: dict = {}
    for f in action.contract.outputs:
        if f.name == "invoiceNumber":
            out[f.name] = str(inputs.get("invoiceId", "INV-0000"))
        elif f.name == "pdfUrl":
            out[f.name] = f"https://files.acme.com/invoices/{inputs.get('invoiceId','INV')}.pdf"
        elif f.name == "supplierName":
            out[f.name] = "Acme Supplies GmbH"
        elif f.name == "amount":
            out[f.name] = 4280.50
        elif f.name == "status":
            out[f.name] = "paid"
        elif f.name == "eta":
            out[f.name] = "2025-02-14"
        elif f.name == "currentLocation":
            out[f.name] = "Rotterdam, NL"
        elif f.name == "proofOfDeliveryUrl":
            out[f.name] = "https://files.maersk.com/pod/POD-8842.pdf"
        elif f.name == "denialReason":
            out[f.name] = None
        elif f.name == "nextStep":
            out[f.name] = "no action needed"
        elif f.name == "lastUpdated":
            out[f.name] = datetime.utcnow().isoformat()
        elif f.type == "number":
            out[f.name] = 0
        elif f.type == "boolean":
            out[f.name] = True
        else:
            out[f.name] = f.name
    return out


class ApiAdapter(ExecutionAdapter):
    """Calls the official vendor REST API."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.api

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        path = f"/api/v1/{action.name}"
        traces = [
            TraceEvent(ts=ts, adapter=AdapterType.api, level="info",
                       message=f"GET {path}", step="http.request", durationMs=40),
            TraceEvent(ts=ts, adapter=AdapterType.api, level="info",
                       message="200 OK", step="http.response", durationMs=80),
            TraceEvent(ts=ts, adapter=AdapterType.api, level="info",
                       message="schema validated", step="validation", durationMs=2),
        ]
        return AdapterResult(
            success=True,
            outputs=_ok_outputs(action, inputs),
            traces=traces,
            screenshots=[],
            error=None,
            durationMs=120,
        )
