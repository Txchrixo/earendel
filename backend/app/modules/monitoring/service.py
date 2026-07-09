"""Monitoring — service: summary stats, repair resolution, canary runs."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ...core.domain.enums import ActionStatus, Caller, ExecutionStatus, RepairStatus
from ...core.domain.entities import RepairProposal, TypedAction
from ...core.repair.knowledge_base import (
    record_outcome as kb_record_outcome,
    store_repair as kb_store_repair,
)
from ...core.repair.knowledge_base import (
    extract_target_domain, infer_intention, infer_widget_type,
)
from ...core.repair.repair_proposer import propose as propose_repair_fn
from ...infrastructure.llm_client import LLMClient
from ...modules.executions.repository import get_execution
from ...shared.errors import NotFoundError, ValidationError
from .repository import (
    get_repair, list_executions, list_repairs, put_repair,
)


async def summary(action_registry) -> dict[str, Any]:
    """Aggregate monitoring stats across actions + executions."""
    actions = action_registry.list()
    total = len(actions)
    healthy = sum(1 for a in actions if a.status == ActionStatus.published)
    degraded = sum(1 for a in actions if a.status == ActionStatus.degraded)
    broken = sum(1 for a in actions if a.status == ActionStatus.broken)

    exe_all = await list_executions()
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent = [e for e in exe_all if e.startedAt >= cutoff]
    successes = sum(1 for e in recent if e.status == ExecutionStatus.success)
    success_rate = round(successes / len(recent), 3) if recent else 1.0

    canary_total = sum(len(a.canary) for a in actions)
    canary_passed = sum(
        1 for a in actions for c in a.canary if c.lastStatus == "passed")
    canary_pass_rate = (round(canary_passed / canary_total, 3)
                        if canary_total else 1.0)

    repairs = await list_repairs()
    open_repairs = sum(1 for r in repairs if r.status == RepairStatus.pending)

    mttr = 3.2  # placeholder MTTR in hours (no real incident timestamps yet)

    return {
        "totalActions": total,
        "healthy": healthy,
        "degraded": degraded,
        "broken": broken,
        "canaryPassRate": canary_pass_rate,
        "openRepairs": open_repairs,
        "executions24h": len(recent),
        "successRate24h": success_rate,
        "mttrHours": mttr,
    }


async def fetch_repairs() -> list[RepairProposal]:
    """Return all repair proposals."""
    return await list_repairs()


async def resolve_repair(
    repair_id: str,
    decision: str,
    action_registry=None,
) -> RepairProposal:
    """Approve / reject / auto-apply a repair proposal.

    Wires the decision back into the cross-client Repair Knowledge Base:

    * ``approved`` / ``auto_applied``:
        - If the proposal is KB-sourced (``source == "knowledge_base"``),
          increment the KB entry's success / autoApplied counters — making
          it even stronger for future queries.
        - If the proposal is LLM-sourced, ALSO store it in the KB so it's
          available for future cross-client queries, then record the
          success outcome on the freshly-stored entry.
        - Fallback-sourced proposals are NOT auto-stored (their confidence
          is too low to be useful for other clients).
    * ``rejected``:
        - Record a failure on the KB entry (when one exists) so the
          combined-score ranking can penalize it.

    All KB IO is best-effort: a DB outage never blocks the resolution —
    the proposal's status is still updated and persisted.
    """
    if decision not in {"approved", "rejected", "auto_applied"}:
        raise ValidationError(f"invalid repair decision: {decision}")
    proposal = await get_repair(repair_id)
    if proposal is None:
        raise NotFoundError("RepairProposal", repair_id)
    proposal.status = RepairStatus(decision)

    # ---- KB outcome recording (best-effort) ----------------------------
    source = (proposal.source or "fallback").lower()
    pattern_key = proposal.patternKey

    if decision in {"approved", "auto_applied"}:
        auto_applied = decision == "auto_applied"
        if source == "knowledge_base" and pattern_key:
            # KB-sourced: just record the outcome (entry already exists).
            await kb_record_outcome(pattern_key, succeeded=True,
                                    auto_applied=auto_applied)
        elif source == "llm":
            # LLM-sourced approved: store it into the KB so future failures
            # benefit, then record the success on the freshly-stored entry.
            # We need the action name to re-infer the (domain, widget,
            # intention) signature — look it up via the registry when
            # available. If the registry isn't passed, we fall back to
            # inferring from the failed selector alone (target_domain /
            # intention will be "unknown" / "generic", which is still
            # useful for cross-client matching on the selector itself).
            action_name = ""
            if action_registry is not None:
                try:
                    action = action_registry.get(proposal.actionId)
                    if action is not None:
                        action_name = action.name
                except Exception:
                    pass
            target_domain = extract_target_domain(action_name)
            widget_type = infer_widget_type(proposal.failedSelector, "")
            intention = infer_intention(action_name, "")
            stored_key = await kb_store_repair(
                proposal, target_domain, widget_type, intention,
            )
            if stored_key:
                proposal.patternKey = stored_key
                await kb_record_outcome(stored_key, succeeded=True,
                                        auto_applied=auto_applied)
    elif decision == "rejected":
        # Only record a failure when we already have a KB entry to fail.
        if pattern_key:
            await kb_record_outcome(pattern_key, succeeded=False)

    return await put_repair(proposal)


async def run_canary(action_registry, orchestrator, action_id: str) -> dict[str, Any]:
    """Re-run an action as caller=canary and return its outcome."""
    action = action_registry.get(action_id)
    if action is None:
        raise NotFoundError("Action", action_id)
    inputs = {f.name: f.default or "canary-sample"
              for f in action.contract.inputs}
    exe = await orchestrator.run(action, inputs, Caller.canary, True)
    return exe.model_dump(mode="json")


async def propose_repair(
    action_registry, llm: LLMClient, action_id: str, execution_id: str
) -> RepairProposal | None:
    """Propose a repair for a failed execution, persist it, and return it.

    Uses the LLM to generate the candidate selector + reasoning (with a
    deterministic fallback). Returns None if the failure wasn't a selector
    error or the action/execution can't be found.
    """
    action = action_registry.get(action_id)
    if action is None:
        raise NotFoundError("Action", action_id)
    exe = await get_execution(execution_id)
    if exe is None:
        raise NotFoundError("Execution", execution_id)
    proposal = await propose_repair_fn(action, exe, llm)
    if proposal is None:
        return None
    return await put_repair(proposal)


async def fetch_repairs_for_action(action_id: str) -> list[RepairProposal]:
    """Return repair proposals for a specific action (used by connector detail)."""
    all_repairs = await list_repairs()
    return [r for r in all_repairs if r.actionId == action_id]
