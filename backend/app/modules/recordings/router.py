"""Recordings — FastAPI router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...api.deps import get_action_registry
from . import service

router = APIRouter(prefix="/recordings", tags=["recordings"])


class CreateRecordingBody(BaseModel):
    """POST body for creating a simulated recording."""
    connectorId: str
    workflowName: str


@router.get("")
async def list_recordings_endpoint() -> list[dict[str, Any]]:
    """List all recordings."""
    items = await service.fetch_all()
    return [r.model_dump(mode="json") for r in items]


@router.get("/{recording_id}")
async def get_recording_endpoint(recording_id: str) -> dict[str, Any]:
    """Fetch a single recording."""
    rec = await service.fetch(recording_id)
    return rec.model_dump(mode="json")


@router.post("")
async def create_recording_endpoint(body: CreateRecordingBody) -> dict[str, Any]:
    """Create a simulated recording."""
    rec = await service.create_simulated(body.connectorId, body.workflowName)
    return rec.model_dump(mode="json")


@router.post("/{recording_id}/compile")
async def compile_recording_endpoint(
    recording_id: str, registry=Depends(get_action_registry)
) -> dict[str, Any]:
    """Compile a recording into a TypedAction and register it."""
    action = await service.compile(recording_id, registry)
    return action.model_dump(mode="json")
