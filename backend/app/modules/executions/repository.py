"""Executions — repository (Prisma ↔ Pydantic)."""
from __future__ import annotations

from ...core.domain.entities import Execution
from ...infrastructure.prisma_repositories import (
    execution_get, execution_list, execution_put,
)


async def list_executions(action_id: str | None = None) -> list[Execution]:
    """Return all executions, optionally filtered by action id."""
    rows = await execution_list(action_id)
    return [Execution.model_validate(r) for r in rows]


async def get_execution(execution_id: str) -> Execution | None:
    """Fetch an execution by id."""
    row = await execution_get(execution_id)
    return Execution.model_validate(row) if row else None


async def put_execution(execution: Execution) -> Execution:
    """Persist an execution."""
    await execution_put(execution.model_dump(mode="json"))
    return execution
