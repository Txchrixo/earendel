"""Engine — orchestrator: selects an adapter, runs, validates, falls back.

The orchestrator is the heart of the multi-adapter execution model.
It never raises; on total failure it escalates to human review.
"""
from __future__ import annotations

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
        chain = list(action.executionMethods) or [AdapterType.api]
        traces: list[TraceEvent] = []
        screenshots: list[str] = []
        outputs: dict | None = None
        chosen: AdapterType = chain[0]
        status = ExecutionStatus.failed
        error: str | None = None
        post_met: bool | None = None

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
            )
            adapter = self._registry.get(adapter_type)
            result: AdapterResult = await adapter.execute(action, inputs, ctx)
            traces.extend(result.traces)
            screenshots.extend(result.screenshots)
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
                    vault=self._vault, telemetry=self._telemetry)
                human_result = await self._registry.get(
                    AdapterType.human).execute(action, inputs, ctx)
                traces.extend(human_result.traces)
                outputs = human_result.outputs
                chosen = AdapterType.human
            status = ExecutionStatus.human_review

        finished = datetime.utcnow()
        return Execution(
            id=new_id("exe"), actionId=action.id, actionName=action.name,
            caller=caller, inputs=inputs, outputs=outputs, adapter=chosen,
            fallbackChain=chain, status=status, durationMs=int(
                (finished - started).total_seconds() * 1000),
            startedAt=started, finishedAt=finished, traces=traces,
            screenshots=screenshots, postconditionsMet=post_met,
            errorMessage=error, riskApproved=risk_approved,
        )
