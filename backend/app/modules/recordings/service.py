"""Recordings — service: list, get, create via simulator, compile → action."""
from __future__ import annotations

from ...core.contracts.schema_compiler import compile_recording
from ...core.domain.entities import Recording, TypedAction
from ...infrastructure.llm_client import LLMClient
from ...modules.connectors.service import fetch as fetch_connector
from ...shared.errors import NotFoundError
from ...shared.ids import new_id
from .repository import get_recording, list_recordings, put_recording
from .simulator import simulate_recording


async def fetch_all() -> list[Recording]:
    """List all recordings."""
    return await list_recordings()


async def fetch(recording_id: str) -> Recording:
    """Fetch a recording or raise NotFoundError."""
    rec = await get_recording(recording_id)
    if rec is None:
        raise NotFoundError("Recording", recording_id)
    return rec


async def create_simulated(connector_id: str, workflow_name: str) -> Recording:
    """Create a recording via the deterministic simulator."""
    await fetch_connector(connector_id)
    rec = simulate_recording(connector_id, workflow_name)
    return await put_recording(rec)


async def compile(recording_id: str, action_registry, llm: LLMClient | None = None
                  ) -> TypedAction:
    """Compile a recording into a TypedAction and register it."""
    rec = await fetch(recording_id)
    if rec.status == "compiled" and rec.compiledActionId:
        existing = action_registry.get(rec.compiledActionId)
        if existing is not None:
            return existing
    connector = await fetch_connector(rec.connectorId)
    action = await compile_recording(rec, connector, llm)
    await action_registry.put(action)
    rec.status = "compiled"
    rec.compiledActionId = action.id
    await put_recording(rec)
    return action
