"""Monitoring — repository for repair proposals + aggregate queries."""
from __future__ import annotations

from ...core.domain.entities import Execution, RepairProposal
from ...infrastructure.database import doc_get, doc_list, doc_put

_REPAIRS = "repairs"
_EXECUTIONS = "executions"


async def list_repairs() -> list[RepairProposal]:
    """Return all repair proposals."""
    rows = await doc_list(_REPAIRS)
    return [RepairProposal.model_validate(r) for r in rows]


async def get_repair(repair_id: str) -> RepairProposal | None:
    """Fetch a single repair proposal by id."""
    row = await doc_get(_REPAIRS, repair_id)
    return RepairProposal.model_validate(row) if row else None


async def put_repair(proposal: RepairProposal) -> RepairProposal:
    """Insert / update a repair proposal."""
    await doc_put(_REPAIRS, proposal.id, proposal.model_dump(mode="json"))
    return proposal


async def list_executions() -> list[Execution]:
    """Return all executions (used for aggregate monitoring stats)."""
    rows = await doc_list(_EXECUTIONS)
    return [Execution.model_validate(r) for r in rows]
