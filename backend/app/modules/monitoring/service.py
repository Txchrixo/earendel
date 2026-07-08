"""Monitoring — service: summary stats, repair resolution, canary runs."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ...core.domain.enums import ActionStatus, Caller, ExecutionStatus, RepairStatus
from ...core.domain.entities import RepairProposal
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


async def resolve_repair(repair_id: str, decision: str) -> RepairProposal:
    """Approve / reject / auto-apply a repair proposal."""
    if decision not in {"approved", "rejected", "auto_applied"}:
        raise ValidationError(f"invalid repair decision: {decision}")
    proposal = await get_repair(repair_id)
    if proposal is None:
        raise NotFoundError("RepairProposal", repair_id)
    proposal.status = RepairStatus(decision)
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
