"""Adapter 3 — Playwright browser workflow (AutoRPA-style).

Deterministically fails ~20% of the time on a selector-not-found error to
demonstrate the repair proposer + fallback chain.
"""
from __future__ import annotations

import hashlib

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from .api_adapter import _ok_outputs
from .base import AdapterResult, ExecutionContext, ExecutionAdapter

_FAILURE_RATE = 0.20


def _should_fail(action: TypedAction, inputs: dict) -> bool:
    """Deterministic 20% failure based on action id + inputs hash."""
    key = f"{action.id}:{sorted(inputs.items())}"
    h = hashlib.sha256(key.encode()).hexdigest()
    return (int(h[:8], 16) % 100) < int(_FAILURE_RATE * 100)


class BrowserAdapter(ExecutionAdapter):
    """Drives a headless Chromium with the action's recorded selectors."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.browser

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        base = [
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message="launch chromium headless", step="launch", durationMs=180),
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message=f"goto https://{action.connectorId}.portal", step="navigate",
                       durationMs=220),
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message="fill login form", step="input", durationMs=120),
        ]
        if _should_fail(action, inputs):
            base.append(TraceEvent(
                ts=ts, adapter=AdapterType.browser, level="error",
                message='selector not found: button[data-testid="download-btn"]',
                step="click", durationMs=380,
            ))
            return AdapterResult(
                success=False, outputs={}, traces=base,
                screenshots=["snap-1.png"], durationMs=900,
                error='selector not found: button[data-testid="download-btn"]',
            )
        base.extend([
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message='click button[data-testid="download-btn"]', step="click",
                       durationMs=110),
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message="waitForDownload", step="download", durationMs=260),
        ])
        return AdapterResult(
            success=True, outputs=_ok_outputs(action, inputs),
            traces=base, screenshots=["snap-1.png", "snap-2.png"],
            error=None, durationMs=900,
        )
