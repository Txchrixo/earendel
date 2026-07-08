"""Publishing — FastAPI router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...api.deps import get_action_registry
from . import service
from .registry_service import build_registry

router = APIRouter(prefix="/publishing", tags=["publishing"])


@router.get("/registry")
async def get_mcp_registry_endpoint(
    registry=Depends(get_action_registry),
) -> dict[str, Any]:
    """Return the full MCP server registry — all published actions as one manifest.

    Includes ready-to-paste config snippets for Claude Desktop, Cursor, and CLI.
    Placed before /{action_id} so FastAPI doesn't treat 'registry' as an id.
    """
    return await build_registry(registry)


@router.get("/{action_id}")
async def get_published_tool_endpoint(
    action_id: str, registry=Depends(get_action_registry)
) -> dict[str, Any]:
    """Return the published tool surface for an action (MCP/REST/SDK)."""
    return await service.get_published_tool(registry, action_id)
