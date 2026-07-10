"""Evaluation module — API endpoints for the benchmark harness."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...api.deps import get_action_registry, get_orchestrator

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/workflows")
async def list_workflows() -> dict[str, Any]:
    """List all benchmark workflows."""
    from ...core.evaluation.harness import BENCHMARK_WORKFLOWS
    return {
        "workflows": [
            {
                "name": wf.name,
                "actionName": wf.action_name,
                "description": wf.description,
                "inputs": wf.inputs,
                "category": wf.category,
                "expectedOutputs": wf.expected_outputs,
                "steps": wf.steps,
                "portalUrl": wf.portal_url,
            }
            for wf in BENCHMARK_WORKFLOWS
        ],
        "total": len(BENCHMARK_WORKFLOWS),
    }


@router.post("/run")
async def run_benchmark(
    runs_per_workflow: int = 5,
    perturbed: bool = False,
    registry=Depends(get_action_registry),
    orchestrator=Depends(get_orchestrator),
) -> dict[str, Any]:
    """Run the full benchmark suite.

    Query params:
    - runs_per_workflow: number of runs per workflow per baseline (default 5, max 20)
    - perturbed: if True, simulate WAREX perturbation (selectors change, popups,
      slower loads). BU per-step success drops 85% → 60%.

    Returns the full benchmark results with latency, success rate, cost,
    and claim verification.
    """
    from ...core.evaluation.harness import run_full_benchmark
    # Cap at 20 runs to prevent abuse
    runs = min(max(runs_per_workflow, 1), 20)
    return await run_full_benchmark(
        registry, orchestrator, runs_per_workflow=runs, perturbed=perturbed,
    )
