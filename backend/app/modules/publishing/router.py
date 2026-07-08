"""Publishing — FastAPI router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...api.deps import get_action_registry
from . import service

router = APIRouter(prefix="/publishing", tags=["publishing"])


@router.get("/{action_id}")
async def get_published_tool_endpoint(
    action_id: str, registry=Depends(get_action_registry)
) -> dict[str, Any]:
    """Return the published tool surface for an action (MCP/REST/SDK)."""
    return await service.get_published_tool(registry, action_id)
