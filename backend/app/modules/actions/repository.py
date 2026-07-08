"""Actions — repository: thin pass-through to the ActionRegistry + doc store."""
from __future__ import annotations

from ...core.domain.entities import TypedAction


async def list_actions(registry) -> list[TypedAction]:
    """Return all actions from the registry."""
    return registry.list()


async def get_action(registry, action_id: str) -> TypedAction | None:
    """Return one action or None."""
    return registry.get(action_id)


async def put_action(registry, action: TypedAction) -> TypedAction:
    """Insert / update an action and persist."""
    return await registry.put(action)
