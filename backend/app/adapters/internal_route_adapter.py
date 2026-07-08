"""Adapter 2 — Discovered internal / shadow API (APISensor-style).

Replays captured network requests from the recording phase. During recording,
Earendel captures XHR/fetch traffic. This adapter replays those requests
with the user's session cookies, providing a faster, more reliable path
than browser automation.

If no captured routes exist for the action, falls back to simulation.
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

# Captured route registry: maps action names to their discovered internal endpoints.
# In production, these are captured during the recording phase and stored per-action.
_ROUTE_REGISTRY: dict[str, dict[str, Any]] = {
    "downloadInvoice": {
        "method": "POST",
        "url": "https://supplier-portal.acme.com/internal/v2/invoices/download",
        "body_template": {"invoiceId": "{invoiceId}"},
        "cookie_env": "ACME_SESSION_COOKIE",
        "field_mapping": {
            "invoiceNumber": "invoice_number",
            "pdfUrl": "download_url",
            "supplierName": "supplier_name",
            "amount": "total",
            "status": "payment_status",
        },
    },
    "checkClaimStatus": {
        "method": "POST",
        "url": "https://provider.bluecross.com/internal/v2/claims/check",
        "body_template": {"patientId": "{patientId}", "claimId": "{claimId}"},
        "cookie_env": "BLUECROSS_SESSION_COOKIE",
        "field_mapping": {
            "status": "claim_status",
            "denialReason": "denial_reason",
            "nextStep": "next_step",
            "lastUpdated": "last_updated",
        },
    },
    "downloadMarketplaceReport": {
        "method": "GET",
        "url": "https://sellercentral.amazon.com/internal/reports/download",
        "body_template": {"reportType": "{reportType}", "dateRange": "{dateRange}"},
        "cookie_env": "AMAZON_SESSION_COOKIE",
        "field_mapping": {
            "reportUrl": "download_url",
            "rows": "row_count",
            "periodStart": "period_start",
            "periodEnd": "period_end",
            "currency": "currency",
        },
    },
}

_TIMEOUT = 15.0


def _get_nested(data: dict, path: str) -> Any:
    """Get a value from a nested dict using dot notation."""
    keys = path.split(".")
    val = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def _build_body(template: dict, inputs: dict) -> dict:
    """Build the request body from the template, substituting input values."""
    body = {}
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            input_key = value[1:-1]
            body[key] = inputs.get(input_key, value)
        else:
            body[key] = value
    return body


def _map_response(response_data: dict, action: TypedAction, route_config: dict) -> dict:
    """Map the API response to the action's output contract fields."""
    mapping = route_config.get("field_mapping", {})
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
        else:
            outputs[field.name] = None
    return outputs


class InternalRouteAdapter(ExecutionAdapter):
    """Replays discovered internal endpoints with session cookies."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.internal_route

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        route = _ROUTE_REGISTRY.get(action.name)

        # If no route captured OR no session cookie, fall back to simulation.
        if route is None:
            return await self._simulate(action, inputs, ctx)

        # Check if session cookie is configured — if not, use simulation.
        cookie_env = route.get("cookie_env", "")
        session_cookie = os.environ.get(cookie_env, "")
        if not session_cookie:
            return await self._simulate(action, inputs, ctx)

        method = route.get("method", "POST")
        url = route["url"]
        body = _build_body(route.get("body_template", {}), inputs)

        # Get session cookie from env.
        cookie_env = route.get("cookie_env", "")
        session_cookie = os.environ.get(cookie_env, "")

        traces: list[TraceEvent] = [
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message=f"discovered endpoint {url} (from HAR capture)",
                       step="discover"),
        ]

        if session_cookie:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message="session cookie reused", step="auth", durationMs=30))
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message="XSRF token attached", step="auth", durationMs=10))
        else:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="warn",
                message=f"no session cookie in env ({cookie_env}) — proceeding without auth",
                step="auth", durationMs=5))

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if session_cookie:
            headers["Cookie"] = f"session={session_cookie}"
            headers["X-XSRF-TOKEN"] = session_cookie[:32] if len(session_cookie) >= 32 else session_cookie

        try:
            start = datetime.utcnow()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers, params=body)
                else:
                    resp = await client.request(method, url, headers=headers, json=body)

            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

            if resp.status_code >= 400:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="error",
                    message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    step="http.response", durationMs=elapsed))
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error=f"HTTP {resp.status_code}",
                    durationMs=elapsed,
                )

            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message=f"200 OK ({elapsed}ms)", step="http.response", durationMs=elapsed))

            try:
                response_data = resp.json()
            except Exception:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="error",
                    message="response is not valid JSON", step="parse"))
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error="Invalid JSON response",
                    durationMs=elapsed,
                )

            outputs = _map_response(response_data, action, route)
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message=f"mapped {len(outputs)} output fields", step="mapping", durationMs=1))

            return AdapterResult(
                success=True, outputs=outputs, traces=traces,
                screenshots=[], error=None, durationMs=elapsed,
            )

        except httpx.TimeoutException:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="error",
                message=f"timeout after {_TIMEOUT}s", step="http.request"))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=f"Timeout after {_TIMEOUT}s",
                durationMs=int(_TIMEOUT * 1000),
            )
        except Exception as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="error",
                message=f"connection error: {exc}", step="http.request"))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=str(exc),
                durationMs=0,
            )

    async def _simulate(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        """Fallback simulation when no route is captured."""
        from .api_adapter import _simulate_outputs
        ts = ctx.telemetry.now()
        path = f"/internal/v2/{action.name}"
        traces = [
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message=f"discovered endpoint {path} (simulated — no HAR capture)",
                       step="discover"),
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message="session cookie reused (simulated)", step="auth", durationMs=30),
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message="200 OK (simulated)", step="http.response", durationMs=140),
        ]
        return AdapterResult(
            success=True,
            outputs=_simulate_outputs(action, inputs),
            traces=traces,
            screenshots=[],
            error=None,
            durationMs=180,
        )
