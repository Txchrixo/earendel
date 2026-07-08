"""Registry — in-memory catalog of TypedActions, backed by Prisma repos."""
from __future__ import annotations

from typing import Iterable

from ...core.domain.entities import TypedAction
from ...infrastructure.prisma_repositories import (
    action_delete, action_get, action_list, action_put,
)


class ActionRegistry:
    """In-memory index of TypedActions with persistence to the Prisma DB."""

    def __init__(self) -> None:
        self._by_id: dict[str, TypedAction] = {}

    async def load(self) -> None:
        """Hydrate the registry from the Prisma TypedAction table on startup."""
        rows = await action_list()
        for row in rows:
            action = TypedAction.model_validate(row)
            self._by_id[action.id] = action

    def list(self) -> list[TypedAction]:
        """Return all registered actions sorted by creation time."""
        return sorted(self._by_id.values(), key=lambda a: a.createdAt)

    def get(self, action_id: str) -> TypedAction | None:
        """Look up an action by id."""
        return self._by_id.get(action_id)

    async def put(self, action: TypedAction) -> TypedAction:
        """Insert or update an action, persisting to the Prisma DB."""
        self._by_id[action.id] = action
        await action_put(action.model_dump(mode="json"))
        return action

    async def remove(self, action_id: str) -> bool:
        """Remove an action from memory and the Prisma DB."""
        if action_id in self._by_id:
            del self._by_id[action_id]
        return await action_delete(action_id)

    def extend(self, actions: Iterable[TypedAction]) -> None:
        """Bulk-insert actions without persisting (used by seed)."""
        for a in actions:
            self._by_id[a.id] = a
