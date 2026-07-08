"""Adapter 5 — Human-in-the-loop review.

Always "succeeds" by producing a review request; the orchestrator marks the
Execution as `human_review` so a human can approve / fill outputs later.
"""
from __future__ import annotations

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from .base import AdapterResult, ExecutionContext, ExecutionAdapter


class HumanAdapter(ExecutionAdapter):
    """Yields control to a human operator with a structured prompt."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.human

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        prompt = (
            f"Manual review requested for action '{action.name}' "
            f"(caller={ctx.caller.value}). Inputs: {inputs}. "
            f"Please confirm and provide the expected outputs."
        )
        traces = [
            TraceEvent(ts=ts, adapter=AdapterType.human, level="warn",
                       message="escalating to human review", step="escalate"),
            TraceEvent(ts=ts, adapter=AdapterType.human, level="info",
                       message=f"review prompt queued: {prompt[:80]}…", step="queue"),
        ]
        return AdapterResult(
            success=True,
            outputs={"_humanReview": True, "prompt": prompt,
                     "actionId": action.id, "inputs": inputs},
            traces=traces,
            screenshots=[],
            error=None,
            durationMs=0,
        )
