"""Recordings — repository (Prisma ↔ Pydantic)."""
from __future__ import annotations

from ...core.domain.entities import Recording
from ...infrastructure.prisma_repositories import (
    recording_delete, recording_get, recording_list, recording_put,
)


async def list_recordings() -> list[Recording]:
    """Return all recordings."""
    rows = await recording_list()
    return [Recording.model_validate(r) for r in rows]


async def get_recording(recording_id: str) -> Recording | None:
    """Fetch a recording by id."""
    row = await recording_get(recording_id)
    return Recording.model_validate(row) if row else None


async def put_recording(recording: Recording) -> Recording:
    """Insert or update a recording."""
    await recording_put(recording.model_dump(mode="json"))
    return recording


async def delete_recording(recording_id: str) -> bool:
    """Delete a recording."""
    return await recording_delete(recording_id)
