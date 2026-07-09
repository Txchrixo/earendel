"""Actions — service: publish, rollback, repair flows."""
from __future__ import annotations

from ...core.domain.entities import TypedAction
from ...core.domain.enums import ActionStatus, PublishTarget
from ...core.repair.repair_proposer import propose as propose_repair
from ...core.repair.selector_healer import apply as apply_repair
from ...core.versioning.version_manager import rollback as rollback_action
from ...infrastructure.llm_client import LLMClient
from ...shared.errors import NotFoundError, ValidationError
from .repository import get_action, put_action


async def fetch(registry, action_id: str) -> TypedAction:
    """Fetch an action or raise NotFoundError."""
    action = await get_action(registry, action_id)
    if action is None:
        raise NotFoundError("Action", action_id)
    return action


async def fetch_all(registry) -> list[TypedAction]:
    """Return all actions."""
    return registry.list()


async def publish(registry, action_id: str, targets: list[PublishTarget]) -> TypedAction:
    """Mark an action as published to the given targets + set mcp tool name."""
    action = await fetch(registry, action_id)
    action.publishedAs = list(set(list(action.publishedAs) + targets))
    if PublishTarget.mcp in targets and not action.mcpToolName:
        action.mcpToolName = f"earendel_{action.name.lower()}"
    action.status = ActionStatus.published
    action.updatedAt = __import__("datetime").datetime.utcnow()
    return await put_action(registry, action)


async def rollback(registry, action_id: str, version: str) -> TypedAction:
    """Roll an action back to a previously released version."""
    action = await fetch(registry, action_id)
    rolled = rollback_action(action, version)
    return await put_action(registry, rolled)


async def propose_repair_for(
    registry, action_id: str, failed_execution, llm: LLMClient | None = None
):
    """Propose a repair for a failed execution of an action."""
    action = await fetch(registry, action_id)
    return await propose_repair(action, failed_execution, llm)


async def apply_repair_to(registry, action_id: str, proposal) -> TypedAction:
    """Apply an approved repair proposal to an action."""
    action = await fetch(registry, action_id)
    healed = apply_repair(action, proposal)
    return await put_action(registry, healed)
