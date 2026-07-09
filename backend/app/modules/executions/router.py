"""Executions — FastAPI router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...api.deps import get_action_registry, get_orchestrator
from ...core.domain.enums import Caller
from . import service

router = APIRouter(prefix="/executions", tags=["executions"])


class RunBody(BaseModel):
    """POST body for running an action."""
    actionId: str
    inputs: dict[str, Any] = {}
    caller: Caller = Caller.manual
    riskApproved: bool = True


@router.get("")
async def list_executions_endpoint(
    actionId: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """List executions, optionally filtered by action id."""
    items = await service.fetch_all(actionId)
    return [e.model_dump(mode="json") for e in items]


@router.get("/{execution_id}")
async def get_execution_endpoint(execution_id: str) -> dict[str, Any]:
    """Fetch a single execution."""
    exe = await service.fetch(execution_id)
    return exe.model_dump(mode="json")


@router.post("")
async def run_execution_endpoint(
    body: RunBody,
    registry=Depends(get_action_registry),
    orchestrator=Depends(get_orchestrator),
) -> dict[str, Any]:
    """Run an action — the primary 'agent calls action' endpoint."""
    exe = await service.run(registry, registry, orchestrator, body.actionId,
                            body.inputs, body.caller, body.riskApproved)
    return exe.model_dump(mode="json")
