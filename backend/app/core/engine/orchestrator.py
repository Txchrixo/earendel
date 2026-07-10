"""Engine — orchestrator: selects an adapter, runs, validates, falls back.

The orchestrator is the heart of the multi-adapter execution model.
It never raises; on total failure it escalates to human review.

Emits real-time events to the execution-stream service via HTTP POST.
"""
from __future__ import annotations

import asyncio
import httpx
from datetime import datetime

from ...adapters.base import AdapterResult, ExecutionContext
from ...core.domain.entities import Execution, TraceEvent, TypedAction
from ...core.domain.enums import AdapterType, Caller, ExecutionStatus
from ...core.domain.value_objects import RISK_POLICY
from ...core.validation.postconditions import validate_outputs
from ...infrastructure.telemetry import TraceCollector
from ...infrastructure.vault import CredentialVault
from ...shared.ids import new_id
from .adapter_registry import AdapterRegistry

# Execution stream service URL.
_STREAM_URL = "http://localhost:3003"


async def _emit_stream(execution_id: str, event: str, payload: dict) -> None:
    """Emit a real-time event to the execution-stream service (non-blocking)."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"{_STREAM_URL}/emit",
                json={"executionId": execution_id, "event": event, "payload": payload},
            )
    except Exception:
        pass  # Stream service unavailable — don't block execution.


class Orchestrator:
    """Runs a TypedAction through its fallback chain, producing an Execution."""

    def __init__(
        self,
        registry: AdapterRegistry,
        action_registry,
        telemetry: TraceCollector | None = None,
    ) -> None:
        self._registry = registry
        self._actions = action_registry
        self._telemetry = telemetry or TraceCollector()
        self._vault = CredentialVault()

    async def run(
        self,
        action: TypedAction,
        inputs: dict,
        caller: Caller,
        risk_approved: bool,
    ) -> Execution:
        """Execute `action` end-to-end, returning a fully populated Execution."""
        run_id = new_id("run")
        started = datetime.utcnow()
        # Default chain: api → internal_route → browser → bu_browser → vision → human.
        # bu_browser is OPTIONAL — it only runs when an action explicitly lists
        # it in executionMethods (or when the chain falls back to this default).
        chain = list(action.executionMethods) or [
            AdapterType.api, AdapterType.internal_route,
            AdapterType.browser, AdapterType.bu_browser,
            AdapterType.vision, AdapterType.human,
        ]
        traces: list[TraceEvent] = []
        screenshots: list[str] = []
        # Phase 3: screenshots captured by prior adapters, forwarded to the
        # next adapter's ExecutionContext so the vision adapter can analyse
        # pages already captured by the browser adapter (instead of falling
        # back to simulation). Full file paths only — the browser adapter
        # converts its filenames to full paths before returning.
        prior_screenshots: list[str] = []
        outputs: dict | None = None
        chosen: AdapterType = chain[0]
        status = ExecutionStatus.failed
        error: str | None = None
        post_met: bool | None = None

        # Emit execution.started event.
        await _emit_stream(run_id, "execution.started", {
            "actionId": action.id,
            "actionName": action.name,
            "inputs": inputs,
            "caller": caller.value,
            "chain": [a.value for a in chain],
        })

        # Risk gate: high/critical actions need approval unless caller is canary.
        policy = RISK_POLICY.get(action.riskLevel)
        needs_human = (
            policy is not None
            and policy.requires_approval
            and not risk_approved
            and caller != Caller.canary
        )
        if needs_human and AdapterType.human not in chain:
            chain = chain + [AdapterType.human]

        for adapter_type in chain:
            if needs_human and adapter_type != AdapterType.human:
                traces.append(TraceEvent(
                    ts=datetime.utcnow(), adapter=adapter_type, level="warn",
                    message="risk approval required — skipping to human review",
                    step="risk.gate"))
                continue
            traces.append(TraceEvent(
                ts=datetime.utcnow(), adapter=adapter_type, level="info",
                message=f"adapter selected: {adapter_type.value}", step="select"))
            ctx = ExecutionContext(
                caller=caller, risk_approved=risk_approved, run_id=run_id,
                vault=self._vault, telemetry=self._telemetry,
                screenshots=prior_screenshots,
            )
            adapter = self._registry.get(adapter_type)
            result: AdapterResult = await adapter.execute(action, inputs, ctx)
            traces.extend(result.traces)
            screenshots.extend(result.screenshots)

            # Collect full screenshot paths for the next adapter in the chain.
            # The browser adapter returns filenames (e.g. "run-123-step-0.png")
            # under /tmp/earendel-screenshots/, but we tolerate full paths
            # too (other adapters may return absolute paths).
            for shot in result.screenshots:
                if shot.startswith("/"):
                    prior_screenshots.append(shot)
                else:
                    prior_screenshots.append(f"/tmp/earendel-screenshots/{shot}")

            # Emit trace events in real-time.
            for trace in result.traces:
                await _emit_stream(run_id, "trace.appended", {
                    "adapter": trace.adapter.value,
                    "level": trace.level,
                    "message": trace.message,
                    "step": trace.step,
                    "durationMs": trace.durationMs,
                })
            chosen = adapter_type
            if not result.success:
                traces.append(TraceEvent(
                    ts=datetime.utcnow(), adapter=adapter_type, level="warn",
                    message=f"adapter failed: {result.error}; falling back",
                    step="fallback"))
                error = result.error
                continue
            ok, reasons = validate_outputs(action, result.outputs)
            post_met = ok
            if not ok:
                traces.append(TraceEvent(
                    ts=datetime.utcnow(), adapter=adapter_type, level="warn",
                    message=f"postconditions failed: {reasons}; falling back",
                    step="postcondition"))
                error = "; ".join(reasons)
                continue
            outputs = result.outputs
            status = (ExecutionStatus.human_review
                      if result.outputs.get("_humanReview")
                      else ExecutionStatus.success)
            error = None
            break
        else:
            # All adapters exhausted without a clean success.
            if chosen != AdapterType.human:
                traces.append(TraceEvent(
                    ts=datetime.utcnow(), adapter=AdapterType.human, level="warn",
                    message="escalating to human review after fallback exhaustion",
                    step="escalate"))
                ctx = ExecutionContext(
                    caller=caller, risk_approved=risk_approved, run_id=run_id,
                    vault=self._vault, telemetry=self._telemetry,
                    screenshots=prior_screenshots,
                )
                human_result = await self._registry.get(
                    AdapterType.human).execute(action, inputs, ctx)
                traces.extend(human_result.traces)
                outputs = human_result.outputs
                chosen = AdapterType.human
            status = ExecutionStatus.human_review

        finished = datetime.utcnow()
        execution = Execution(
            id=new_id("exe"), actionId=action.id, actionName=action.name,
            caller=caller, inputs=inputs, outputs=outputs, adapter=chosen,
            fallbackChain=chain, status=status, durationMs=int(
                (finished - started).total_seconds() * 1000),
            startedAt=started, finishedAt=finished, traces=traces,
            screenshots=screenshots, postconditionsMet=post_met,
            errorMessage=error, riskApproved=risk_approved,
        )

        # Emit execution.completed event.
        await _emit_stream(execution.id, "execution.completed", {
            "status": execution.status.value,
            "adapter": execution.adapter.value,
            "durationMs": execution.durationMs,
            "outputs": outputs,
            "error": error,
            "postconditionsMet": post_met,
        })

        # Phase 9: record Prometheus metrics
        try:
            from ...infrastructure.observability.metrics import record_execution
            record_execution(
                adapter=execution.adapter.value,
                status=execution.status.value,
                caller=caller.value,
                duration_ms=execution.durationMs,
            )
        except Exception:
            pass  # metrics never block execution

        return execution
