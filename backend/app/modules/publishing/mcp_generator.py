"""Publishing — MCP tool definition generator from a TypedAction contract."""
from __future__ import annotations

from typing import Any

from ...core.domain.entities import TypedAction

# JSON Schema → MCP input schema mapping.
_TYPE_MAP = {
    "string": "string", "number": "number", "boolean": "boolean",
    "date": "string", "url": "string", "enum": "string", "file": "string",
}


def build_mcp_definition(action: TypedAction) -> dict[str, Any]:
    """Build a Model Context Protocol tool definition from an action contract."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for f in action.contract.inputs:
        properties[f.name] = {
            "type": _TYPE_MAP.get(f.type, "string"),
            "description": f.description or f.name,
        }
        if f.enum:
            properties[f.name]["enum"] = list(f.enum)
        if f.required:
            required.append(f.name)
    return {
        "name": action.mcpToolName or f"earendel_{action.name.lower()}",
        "description": action.description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                f.name: {"type": _TYPE_MAP.get(f.type, "string")}
                for f in action.contract.outputs
            },
        },
    }


def build_sdk_snippet(action: TypedAction) -> str:
    """Build a TypeScript SDK snippet for calling this action."""
    args = ", ".join(f"{f.name}: string" for f in action.contract.inputs)
    params = ", ".join(f"{f.name}: {f.name}" for f in action.contract.inputs)
    return (
        f"import {{ Earendel }} from '@earendel/sdk';\n\n"
        f"const client = new Earendel('{{apiKey}}');\n\n"
        f"const result = await client.actions.{action.name}({{\n"
        f"  {params}\n"
        f"}});\n"
        f"console.log(result);\n"
    )


def build_rest_endpoint(action: TypedAction) -> str:
    """Return the REST endpoint URL for this action."""
    return f"https://api.earendel.io/v1/actions/{action.id}/run"
