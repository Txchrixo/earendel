"""Executions — service: run an action via the orchestrator + persist."""
from __future__ import annotations

from ...core.domain.entities import Execution
from ...core.domain.enums import Caller
from ...modules.actions.service import fetch as fetch_action
from ...shared.errors import NotFoundError, ValidationError
from .repository import get_execution, list_executions, put_execution


async def fetch_all(action_id: str | None = None) -> list[Execution]:
    """List executions, optionally filtered by action id."""
    return await list_executions(action_id)


async def fetch(execution_id: str) -> Execution:
    """Fetch a single execution or raise NotFoundError."""
    exe = await get_execution(execution_id)
    if exe is None:
        raise NotFoundError("Execution", execution_id)
    return exe


async def run(
    registry, action_registry, orchestrator,
    action_id: str, inputs: dict, caller: Caller, risk_approved: bool,
) -> Execution:
    """Execute an action through the orchestrator and persist the result."""
    action = await fetch_action(action_registry, action_id)
    if action.status == "broken":
        raise ValidationError(f"action {action_id} is broken")
    execution = await orchestrator.run(action, inputs, caller, risk_approved)
    return await put_execution(execution)
