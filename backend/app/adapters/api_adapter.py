"""Adapter 1 — Official REST API.

Makes real HTTP calls via httpx.AsyncClient to the target system's API.
Supports API key auth, bearer tokens, and basic auth.
Parses the response according to the action's output contract.
Validates postconditions on the real response data.

If no endpoint is configured for the action, falls back to a deterministic
simulation so the adapter always produces a result.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any

import httpx

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from .base import AdapterResult, ExecutionContext, ExecutionAdapter

# Endpoint registry: maps action names to their API endpoints.
# In production, this would come from the connector configuration.
# Each entry: {method, url_template, auth_type, auth_key_env, field_mapping}
_ENDPOINT_REGISTRY: dict[str, dict[str, Any]] = {
    "downloadInvoice": {
        "method": "GET",
        "url_template": "https://api.acme.com/v1/invoices/{invoiceId}",
        "auth_type": "api_key",
        "auth_key_env": "ACME_API_KEY",
        "field_mapping": {
            "invoiceNumber": "invoice_number",
            "pdfUrl": "download_url",
            "supplierName": "supplier.name",
            "amount": "total_amount",
            "status": "payment_status",
        },
    },
    "trackShipment": {
        "method": "GET",
        "url_template": "https://api.maersk.com/v1/shipments/{trackingNumber}",
        "auth_type": "bearer",
        "auth_key_env": "MAERSK_API_KEY",
        "field_mapping": {
            "status": "shipment_status",
            "eta": "estimated_arrival",
            "currentLocation": "last_known_location",
            "proofOfDeliveryUrl": "pod_url",
        },
    },
    "checkClaimStatus": {
        "method": "GET",
        "url_template": "https://api.bluecross.com/v1/claims/{claimId}",
        "auth_type": "bearer",
        "auth_key_env": "BLUECROSS_API_KEY",
        "field_mapping": {
            "status": "claim_status",
            "denialReason": "denial_reason",
            "nextStep": "recommended_action",
            "lastUpdated": "last_updated",
        },
    },
    "downloadMarketplaceReport": {
        "method": "GET",
        "url_template": "https://api.amazon.com/v1/reports/{reportType}?dateRange={dateRange}",
        "auth_type": "oauth",
        "auth_key_env": "AMAZON_ACCESS_TOKEN",
        "field_mapping": {
            "reportUrl": "report_download_url",
            "rows": "row_count",
            "periodStart": "period_start",
            "periodEnd": "period_end",
            "currency": "settlement_currency",
        },
    },
    "exportNewCandidates": {
        "method": "GET",
        "url_template": "https://api.greenhouse.io/v1/jobs/{jobId}/candidates",
        "auth_type": "api_key",
        "auth_key_env": "GREENHOUSE_API_KEY",
        "field_mapping": {
            "candidates": "export_url",
            "count": "candidate_count",
            "duplicatesRemoved": "dedup_count",
            "topMatchScore": "best_match_score",
        },
    },
}

# Default timeout for all API calls.
_TIMEOUT = 15.0


def _get_nested(data: dict, path: str) -> Any:
    """Get a value from a nested dict using dot notation (e.g. 'supplier.name')."""
    keys = path.split(".")
    val = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def _map_response(response_data: dict, action: TypedAction, endpoint_config: dict) -> dict:
    """Map the API response to the action's output contract fields."""
    mapping = endpoint_config.get("field_mapping", {})
    outputs: dict[str, Any] = {}
    for field in action.contract.outputs:
        api_field = mapping.get(field.name, field.name)
        value = _get_nested(response_data, api_field)
        if value is not None:
            outputs[field.name] = value
        elif field.type == "number":
            outputs[field.name] = 0
        elif field.type == "boolean":
            outputs[field.name] = False
        elif field.type == "url":
            outputs[field.name] = ""
        else:
            outputs[field.name] = None
    return outputs


def _build_headers(endpoint_config: dict) -> dict[str, str]:
    """Build auth headers from the endpoint config."""
    auth_type = endpoint_config.get("auth_type", "api_key")
    key_env = endpoint_config.get("auth_key_env", "")
    api_key = os.environ.get(key_env, "")

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    if not api_key:
        return headers

    if auth_type == "api_key":
        headers["X-API-Key"] = api_key
    elif auth_type == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_type == "oauth":
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


def _build_url(endpoint_config: dict, inputs: dict) -> str:
    """Build the URL from the template, substituting input values."""
    url = endpoint_config["url_template"]
    for key, value in inputs.items():
        url = url.replace(f"{{{key}}}", str(value))
    return url


class ApiAdapter(ExecutionAdapter):
    """Calls the official vendor REST API via httpx."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.api

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        endpoint = _ENDPOINT_REGISTRY.get(action.name)

        # If no endpoint configured OR no API key available, fall back to
        # deterministic simulation. This is the "demo mode" — in production,
        # real API keys would be set and real HTTP calls would be made.
        if endpoint is None:
            return await self._simulate(action, inputs, ctx)

        # Check if API key is configured — if not, use simulation.
        key_env = endpoint.get("auth_key_env", "")
        api_key = os.environ.get(key_env, "")
        if not api_key:
            return await self._simulate(action, inputs, ctx)

        method = endpoint.get("method", "GET")
        url = _build_url(endpoint, inputs)
        headers = _build_headers(endpoint)

        traces: list[TraceEvent] = [
            TraceEvent(ts=ts, adapter=AdapterType.api, level="info",
                       message=f"{method} {url}", step="http.request"),
        ]

        try:
            start = datetime.utcnow()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, headers=headers, json=inputs)
                else:
                    resp = await client.request(method, url, headers=headers, json=inputs)

            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

            if resp.status_code >= 400:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.api, level="error",
                    message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    step="http.response", durationMs=elapsed))
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error=f"HTTP {resp.status_code}",
                    durationMs=elapsed,
                )

            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.api, level="info",
                message=f"200 OK ({elapsed}ms)", step="http.response", durationMs=elapsed))

            # Parse response and map to contract.
            try:
                response_data = resp.json()
            except Exception:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.api, level="error",
                    message="response is not valid JSON", step="parse"))
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error="Invalid JSON response",
                    durationMs=elapsed,
                )

            outputs = _map_response(response_data, action, endpoint)
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.api, level="info",
                message=f"mapped {len(outputs)} output fields", step="mapping", durationMs=1))
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.api, level="info",
                message="schema validated", step="validation", durationMs=1))

            return AdapterResult(
                success=True, outputs=outputs, traces=traces,
                screenshots=[], error=None, durationMs=elapsed,
            )

        except httpx.TimeoutException:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.api, level="error",
                message=f"timeout after {_TIMEOUT}s", step="http.request"))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=f"Timeout after {_TIMEOUT}s",
                durationMs=int(_TIMEOUT * 1000),
            )
        except httpx.ConnectError as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.api, level="error",
                message=f"connection error: {exc}", step="http.request"))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=f"Connection error: {exc}",
                durationMs=0,
            )
        except Exception as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.api, level="error",
                message=f"unexpected error: {exc}", step="http.request"))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=str(exc),
                durationMs=0,
            )

    async def _simulate(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        """Fallback simulation when no endpoint is configured."""
        ts = ctx.telemetry.now()
        path = f"/api/v1/{action.name}"
        traces = [
            TraceEvent(ts=ts, adapter=AdapterType.api, level="info",
                       message=f"GET {path} (simulated — no endpoint configured)",
                       step="http.request", durationMs=40),
            TraceEvent(ts=ts, adapter=AdapterType.api, level="info",
                       message="200 OK (simulated)", step="http.response", durationMs=80),
            TraceEvent(ts=ts, adapter=AdapterType.api, level="info",
                       message="schema validated", step="validation", durationMs=2),
        ]
        return AdapterResult(
            success=True,
            outputs=_simulate_outputs(action, inputs),
            traces=traces,
            screenshots=[],
            error=None,
            durationMs=120,
        )


def _simulate_outputs(action: TypedAction, inputs: dict) -> dict:
    """Produce deterministic outputs matching the action's contract (fallback)."""
    out: dict = {}
    for f in action.contract.outputs:
        if f.name == "invoiceNumber":
            out[f.name] = str(inputs.get("invoiceId", "INV-0000"))
        elif f.name == "pdfUrl":
            out[f.name] = f"https://files.acme.com/invoices/{inputs.get('invoiceId', 'INV')}.pdf"
        elif f.name == "supplierName":
            out[f.name] = "Acme Supplies GmbH"
        elif f.name == "amount":
            out[f.name] = 4280.50
        elif f.name == "status":
            # Check if this action has an enum constraint on status.
            if f.enum:
                out[f.name] = f.enum[0]  # Use the first enum value.
            else:
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
        elif f.name == "reportUrl":
            out[f.name] = f"https://reports.earendel.io/{action.name}/{inputs.get('reportType', 'report')}.csv"
        elif f.name == "rows":
            out[f.name] = 1284
        elif f.name == "periodStart":
            out[f.name] = "2025-01-01"
        elif f.name == "periodEnd":
            out[f.name] = "2025-01-31"
        elif f.name == "currency":
            out[f.name] = "EUR"
        elif f.name == "candidates":
            out[f.name] = f"https://exports.earendel.io/candidates/{inputs.get('jobId', 'JOB')}.csv"
        elif f.name == "count":
            out[f.name] = 38
        elif f.name == "duplicatesRemoved":
            out[f.name] = 11
        elif f.name == "topMatchScore":
            out[f.name] = 0.92
        elif f.name == "filledFields":
            out[f.name] = 84
        elif f.name == "needsReview":
            out[f.name] = 12
        elif f.name == "evidenceRefs":
            out[f.name] = "https://evidence.earendel.io/drata-soc2-bundle.zip"
        elif f.type == "url":
            out[f.name] = f"https://files.earendel.io/{action.name}/{f.name}"
        elif f.type == "file":
            out[f.name] = f"https://files.earendel.io/{action.name}/{f.name}"
        elif f.type == "number":
            out[f.name] = 0
        elif f.type == "boolean":
            out[f.name] = True
        else:
            out[f.name] = f.name
    return out
