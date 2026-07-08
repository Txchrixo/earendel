"""Adapter 2 — Discovered internal / shadow API (APISensor-style).

Simulates a reverse-engineered internal endpoint discovered from HAR
captures. Faster than browser but unofficial, so gated behind medium risk.
"""
from __future__ import annotations

from datetime import datetime

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from .api_adapter import _ok_outputs
from .base import AdapterResult, ExecutionContext, ExecutionAdapter


class InternalRouteAdapter(ExecutionAdapter):
    """Calls a discovered internal endpoint with reused session cookies."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.internal_route

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        path = f"/internal/v2/{action.name}"
        traces = [
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message=f"discovered endpoint {path} (from HAR)", step="discover"),
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message="session cookie reused", step="auth", durationMs=30),
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message="XSRF token attached", step="auth", durationMs=10),
            TraceEvent(ts=ts, adapter=AdapterType.internal_route, level="info",
                       message="200 OK", step="http.response", durationMs=140),
        ]
        return AdapterResult(
            success=True,
            outputs=_ok_outputs(action, inputs),
            traces=traces,
            screenshots=[],
            error=None,
            durationMs=180,
        )
