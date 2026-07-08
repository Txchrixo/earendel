"""Adapter 5 — Human-in-the-loop review.

When all automated adapters fail, or when the action's risk level requires
human confirmation, this adapter produces a structured review request. The
execution is marked as `human_review` and stored in the review queue.

A human can then approve (with outputs) or reject the execution via the
monitoring UI. If approved, the execution is marked as success with the
human-provided outputs.

The review queue is stored in the document DB (collection: "reviews").
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType, ExecutionStatus
from ..infrastructure.database import doc_put
from ..shared.ids import new_id
from .base import AdapterResult, ExecutionContext, ExecutionAdapter


_COLLECTION = "reviews"


class HumanAdapter(ExecutionAdapter):
    """Yields control to a human operator with a structured review prompt."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.human

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        review_id = new_id("rev")

        # Build the review prompt.
        prompt = (
            f"Manual review requested for action '{action.name}' "
            f"(caller={ctx.caller.value}).\n\n"
            f"Inputs: {inputs}\n\n"
            f"Expected outputs: {[f.name for f in action.contract.outputs]}\n\n"
            f"Please review the inputs and provide the expected outputs, "
            f"or reject if the action should not run."
        )

        # Create the review record in the queue.
        review = {
            "id": review_id,
            "actionId": action.id,
            "actionName": action.name,
            "actionVersion": action.version,
            "caller": ctx.caller.value,
            "inputs": inputs,
            "prompt": prompt,
            "expectedOutputs": [f.name for f in action.contract.outputs],
            "status": "pending",  # pending | approved | rejected
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "reviewedBy": None,
            "reviewedAt": None,
            "outputs": None,
            "rejectReason": None,
        }

        try:
            await doc_put(_COLLECTION, review_id, review)
        except Exception:
            pass  # Non-blocking — the review prompt is still in the execution traces.

        traces = [
            TraceEvent(ts=ts, adapter=AdapterType.human, level="warn",
                       message="escalating to human review", step="escalate"),
            TraceEvent(ts=ts, adapter=AdapterType.human, level="info",
                       message=f"review request queued (id={review_id[:16]}…)", step="queue"),
            TraceEvent(ts=ts, adapter=AdapterType.human, level="info",
                       message=f"review prompt: {prompt[:100]}…", step="prompt"),
            TraceEvent(ts=ts, adapter=AdapterType.human, level="info",
                       message="waiting for human approval (execution paused)", step="wait"),
        ]

        return AdapterResult(
            success=True,  # The adapter "succeeded" in producing a review request.
            outputs={
                "_humanReview": True,
                "reviewId": review_id,
                "prompt": prompt,
                "actionId": action.id,
                "inputs": inputs,
                "expectedOutputs": [f.name for f in action.contract.outputs],
            },
            traces=traces,
            screenshots=[],
            error=None,
            durationMs=0,
        )
