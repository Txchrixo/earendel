"""Phase 6 — Real Canary Scheduler.

Runs canary executions for every published/testing action on a fixed interval
(default: every 15 minutes). Uses APScheduler's AsyncIOScheduler so canaries
run in the same event loop as the FastAPI app.

When a canary fails, the scheduler auto-triggers the repair proposer so the
repair flywheel kicks in without human intervention.

Academic grounding:
- Automated Canary Deployments in Continuous Delivery (2024)
- CanaryAdvisor: A Statistical-Based Tool for Canary Testing (ACM 2015)
- WAREX (arXiv:2510.03285, 2025) — reliability re-evaluation under perturbation
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..domain.enums import ActionStatus, Caller
from ...core.repair.repair_proposer import propose as propose_repair
from ...infrastructure.llm_client import LLMClient

logger = logging.getLogger("earendel.canary")

# Module-level scheduler instance.
_scheduler: AsyncIOScheduler | None = None

# Default canary interval: 15 minutes.
DEFAULT_INTERVAL_MINUTES = 15


async def run_all_canaries(
    action_registry,
    orchestrator,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Run a canary execution for every published/testing action.

    For each action:
    1. Run it via the orchestrator with caller=canary, risk_approved=True
    2. Persist the execution (so it appears in the dashboard + timeseries)
    3. If it fails, auto-trigger the repair proposer

    Returns a summary: {total, succeeded, failed, repairs_proposed}.
    """
    from ...modules.executions.repository import put_execution
    from ...modules.monitoring.repository import repair_put

    actions = []
    for action in action_registry.list():
        if action.status in (ActionStatus.published, ActionStatus.testing):
            actions.append(action)

    if not actions:
        logger.info("canary: no published/testing actions — skipping")
        return {"total": 0, "succeeded": 0, "failed": 0, "repairs_proposed": 0}

    logger.info("canary: running %d actions", len(actions))

    succeeded = 0
    failed = 0
    repairs_proposed = 0

    for action in actions:
        try:
            # Build canary inputs: use field defaults or "canary-sample"
            inputs = {f.name: (f.default or "canary-sample")
                      for f in action.contract.inputs}

            exe = await orchestrator.run(action, inputs, Caller.canary, True)

            # Persist the execution so it shows up in the dashboard + timeseries
            try:
                await put_execution(exe.model_dump(mode="json"))
            except Exception as exc:
                logger.warning("canary: failed to persist execution for %s: %s",
                               action.name, exc)

            if exe.status.value == "success":
                succeeded += 1
                logger.info("canary: %s — SUCCESS (%dms)", action.name, exe.durationMs)
            else:
                failed += 1
                logger.warning("canary: %s — %s (%s)",
                               action.name, exe.status.value,
                               exe.errorMessage or "no error")

                # Auto-trigger repair proposer for selector failures
                if exe.errorMessage and "selector" in exe.errorMessage.lower():
                    try:
                        llm_client = llm or LLMClient()
                        proposal = await propose_repair(
                            action, exe, llm=llm_client)
                        if proposal is not None:
                            await repair_put(proposal.model_dump(mode="json"))
                            repairs_proposed += 1
                            logger.info("canary: auto-proposed repair for %s "
                                        "(selector=%s, confidence=%.2f)",
                                        action.name,
                                        proposal.candidateSelector,
                                        proposal.confidence)
                    except Exception as exc:
                        logger.warning("canary: repair proposal failed for %s: %s",
                                       action.name, exc)

        except Exception as exc:
            failed += 1
            logger.error("canary: %s — exception: %s", action.name, exc)

    summary = {
        "total": len(actions),
        "succeeded": succeeded,
        "failed": failed,
        "repairs_proposed": repairs_proposed,
    }
    logger.info("canary: complete — %s", summary)
    return summary


def start_canary_scheduler(
    action_registry,
    orchestrator,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    llm: LLMClient | None = None,
) -> AsyncIOScheduler:
    """Start the canary scheduler.

    Runs ``run_all_canaries`` every ``interval_minutes`` minutes.
    The scheduler is idempotent: calling this twice replaces the existing job.
    """
    global _scheduler

    if _scheduler is not None:
        logger.info("canary scheduler already running — replacing job")
        _scheduler.shutdown(wait=False)

    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        run_all_canaries,
        IntervalTrigger(minutes=interval_minutes),
        id="canary-runner",
        replace_existing=True,
        args=[action_registry, orchestrator, llm],
        # Don't pile up if a run takes longer than the interval
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()
    logger.info("canary scheduler started — interval=%d minutes", interval_minutes)
    return _scheduler


def stop_canary_scheduler() -> None:
    """Stop the canary scheduler if it's running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("canary scheduler stopped")


def get_scheduler_status() -> dict[str, Any]:
    """Return the current scheduler status for the dashboard."""
    if _scheduler is None:
        return {"running": False, "nextRun": None, "interval": None}
    jobs = _scheduler.get_jobs()
    if not jobs:
        return {"running": True, "nextRun": None, "interval": None}
    job = jobs[0]
    next_run = job.next_run_time
    return {
        "running": True,
        "nextRun": next_run.isoformat() + "Z" if next_run else None,
        "interval": str(job.trigger),
    }
