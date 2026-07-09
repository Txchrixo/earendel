"""Actions — FastAPI router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...api.deps import get_action_registry
from ...core.domain.enums import PublishTarget
from . import service

router = APIRouter(prefix="/actions", tags=["actions"])


class PublishBody(BaseModel):
    """POST body for publishing an action."""
    targets: list[PublishTarget]


class RollbackBody(BaseModel):
    """POST body for rolling an action back."""
    version: str


@router.get("")
async def list_actions_endpoint(
    registry=Depends(get_action_registry),
    connectorId: str | None = None,
) -> list[dict[str, Any]]:
    """List all actions, optionally filtered by connectorId."""
    items = await service.fetch_all(registry)
    if connectorId:
        items = [a for a in items if a.connectorId == connectorId]
    return [a.model_dump(mode="json") for a in items]


@router.get("/{action_id}")
async def get_action_endpoint(action_id: str,
                              registry=Depends(get_action_registry)
                              ) -> dict[str, Any]:
    """Fetch a single action."""
    action = await service.fetch(registry, action_id)
    return action.model_dump(mode="json")


@router.post("/{action_id}/publish")
async def publish_action_endpoint(
    action_id: str, body: PublishBody,
    registry=Depends(get_action_registry),
) -> dict[str, Any]:
    """Publish an action to MCP / REST / SDK."""
    action = await service.publish(registry, action_id, body.targets)
    return action.model_dump(mode="json")


@router.post("/{action_id}/rollback")
async def rollback_action_endpoint(
    action_id: str, body: RollbackBody,
    registry=Depends(get_action_registry),
) -> dict[str, Any]:
    """Roll an action back to a previously released version."""
    action = await service.rollback(registry, action_id, body.version)
    return action.model_dump(mode="json")
