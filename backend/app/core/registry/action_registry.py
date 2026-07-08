"""Registry — in-memory catalog of TypedActions, backed by the doc store."""
from __future__ import annotations

from typing import Iterable

from ...core.domain.entities import TypedAction
from ...infrastructure.database import doc_delete, doc_get, doc_list, doc_put

_COLLECTION = "actions"


class ActionRegistry:
    """In-memory index of TypedActions with persistence to the doc store."""

    def __init__(self) -> None:
        self._by_id: dict[str, TypedAction] = {}

    async def load(self) -> None:
        """Hydrate the registry from the document store on startup."""
        rows = await doc_list(_COLLECTION)
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
        """Insert or update an action, persisting to the doc store."""
        self._by_id[action.id] = action
        await doc_put(_COLLECTION, action.id, action.model_dump(mode="json"))
        return action

    async def remove(self, action_id: str) -> bool:
        """Remove an action from memory and the doc store."""
        if action_id in self._by_id:
            del self._by_id[action_id]
        return await doc_delete(_COLLECTION, action_id)

    def extend(self, actions: Iterable[TypedAction]) -> None:
        """Bulk-insert actions without persisting (used by seed)."""
        for a in actions:
            self._by_id[a.id] = a
