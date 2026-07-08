"""Monitoring — repository for repair proposals + aggregate queries."""
from __future__ import annotations

from ...core.domain.entities import Execution, RepairProposal
from ...infrastructure.prisma_repositories import (
    execution_list, repair_get, repair_list, repair_put,
)


async def list_repairs() -> list[RepairProposal]:
    """Return all repair proposals."""
    rows = await repair_list()
    return [RepairProposal.model_validate(r) for r in rows]


async def get_repair(repair_id: str) -> RepairProposal | None:
    """Fetch a single repair proposal by id."""
    row = await repair_get(repair_id)
    return RepairProposal.model_validate(row) if row else None


async def put_repair(proposal: RepairProposal) -> RepairProposal:
    """Insert / update a repair proposal."""
    await repair_put(proposal.model_dump(mode="json"))
    return proposal


async def list_executions() -> list[Execution]:
    """Return all executions (used for aggregate monitoring stats)."""
    rows = await execution_list()
    return [Execution.model_validate(r) for r in rows]
