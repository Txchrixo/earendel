"""Publishing — service: build published tool surface (MCP/REST/SDK/webhook)."""
from __future__ import annotations

from typing import Any

from ...core.domain.entities import TypedAction
from ...modules.actions.service import fetch as fetch_action
from .mcp_generator import build_mcp_definition, build_rest_endpoint, build_sdk_snippet


async def get_published_tool(registry, action_id: str) -> dict[str, Any]:
    """Return the full published tool surface for an action."""
    action: TypedAction = await fetch_action(registry, action_id)
    return {
        "actionId": action.id,
        "name": action.name,
        "version": action.version,
        "publishedAs": [t.value for t in action.publishedAs],
        "mcpToolName": action.mcpToolName,
        "restEndpoint": build_rest_endpoint(action),
        "sdkSnippet": build_sdk_snippet(action),
        "mcpDefinition": build_mcp_definition(action),
        "webhookUrl": f"https://api.earendel.io/v1/webhooks/{action.id}",
        "contract": action.contract.model_dump(mode="json"),
    }
