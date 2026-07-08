"""Executions — repository (doc-store ↔ Pydantic)."""
from __future__ import annotations

from ...core.domain.entities import Execution
from ...infrastructure.database import doc_get, doc_list, doc_put

_COLLECTION = "executions"


async def list_executions(action_id: str | None = None) -> list[Execution]:
    """Return all executions, optionally filtered by action id."""
    rows = await doc_list(_COLLECTION)
    items = [Execution.model_validate(r) for r in rows]
    if action_id:
        items = [e for e in items if e.actionId == action_id]
    return items


async def get_execution(execution_id: str) -> Execution | None:
    """Fetch an execution by id."""
    row = await doc_get(_COLLECTION, execution_id)
    return Execution.model_validate(row) if row else None


async def put_execution(execution: Execution) -> Execution:
    """Persist an execution."""
    await doc_put(_COLLECTION, execution.id, execution.model_dump(mode="json"))
    return execution
