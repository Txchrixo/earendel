"""Monitoring — FastAPI router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...api.deps import get_action_registry, get_orchestrator
from . import service

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class ResolveBody(BaseModel):
    """POST body for resolving a repair proposal."""
    decision: str


class CanaryBody(BaseModel):
    """POST body for triggering a canary run."""
    actionId: str


@router.get("/summary")
async def summary_endpoint(
    registry=Depends(get_action_registry),
) -> dict[str, Any]:
    """Aggregate monitoring summary."""
    return await service.summary(registry)


@router.get("/repairs")
async def list_repairs_endpoint() -> list[dict[str, Any]]:
    """List all repair proposals."""
    items = await service.fetch_repairs()
    return [r.model_dump(mode="json") for r in items]


@router.post("/repairs/{repair_id}/resolve")
async def resolve_repair_endpoint(
    repair_id: str, body: ResolveBody,
) -> dict[str, Any]:
    """Approve / reject / auto-apply a repair proposal."""
    proposal = await service.resolve_repair(repair_id, body.decision)
    return proposal.model_dump(mode="json")


@router.post("/canary/run")
async def canary_run_endpoint(
    body: CanaryBody,
    registry=Depends(get_action_registry),
    orchestrator=Depends(get_orchestrator),
) -> dict[str, Any]:
    """Trigger a canary execution of an action."""
    return await service.run_canary(registry, orchestrator, body.actionId)
