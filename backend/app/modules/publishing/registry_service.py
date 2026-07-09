"""Publishing — MCP registry: aggregate all published actions as one MCP server."""
from __future__ import annotations

from typing import Any

from ...core.domain.entities import TypedAction
from ...core.domain.enums import PublishTarget
from .mcp_generator import build_mcp_definition


def _claude_config(tools: list[dict[str, Any]]) -> str:
    """Build a Claude Desktop config snippet for the Earendel MCP server."""
    import json
    return json.dumps({
        "mcpServers": {
            "earendel": {
                "command": "npx",
                "args": ["-y", "@earendel/mcp-server"],
                "env": {
                    "EARENDEL_API_URL": "https://api.earendel.io",
                    "EARENDEL_API_KEY": "your-api-key",
                },
            }
        }
    }, indent=2)


def _cursor_config() -> str:
    """Build a Cursor mcp.json snippet."""
    import json
    return json.dumps({
        "mcpServers": {
            "earendel": {
                "url": "https://api.earendel.io/v1/mcp/sse",
                "headers": {"Authorization": "Bearer your-api-key"},
            }
        }
    }, indent=2)


def _curl_install() -> str:
    """One-line install for the Earendel MCP server via curl."""
    return (
        "curl -fsSL https://earendel.io/install | sh && "
        "earendel mcp register --server-name earendel"
    )


async def build_registry(registry) -> dict[str, Any]:
    """Build the full MCP registry from all published actions.

    Returns the MCP server manifest (tools list) + a human-readable registry
    index + ready-to-paste config snippets for Claude Desktop, Cursor, and CLI.
    """
    actions: list[TypedAction] = [
        a for a in registry.list()
        if PublishTarget.mcp in a.publishedAs
    ]

    tools = [build_mcp_definition(a) for a in actions]
    registry_index = [
        {
            "actionId": a.id,
            "name": a.name,
            "description": a.description,
            "category": a.category.value,
            "version": a.version,
            "riskLevel": a.riskLevel.value,
            "mcpToolName": a.mcpToolName or f"earendel_{a.name.lower()}",
        }
        for a in actions
    ]

    return {
        "serverName": "earendel",
        "serverVersion": "0.1.0",
        "protocolVersion": "2024-11-05",
        "tools": tools,
        "registry": registry_index,
        "claudeConfig": _claude_config(tools),
        "cursorConfig": _cursor_config(),
        "curlInstall": _curl_install(),
    }
