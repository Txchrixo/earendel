"""Recordings — repository (doc-store ↔ Pydantic)."""
from __future__ import annotations

from ...core.domain.entities import Recording
from ...infrastructure.database import doc_delete, doc_get, doc_list, doc_put

_COLLECTION = "recordings"


async def list_recordings() -> list[Recording]:
    """Return all recordings."""
    rows = await doc_list(_COLLECTION)
    return [Recording.model_validate(r) for r in rows]


async def get_recording(recording_id: str) -> Recording | None:
    """Fetch a recording by id."""
    row = await doc_get(_COLLECTION, recording_id)
    return Recording.model_validate(row) if row else None


async def put_recording(recording: Recording) -> Recording:
    """Insert or update a recording."""
    await doc_put(_COLLECTION, recording.id, recording.model_dump(mode="json"))
    return recording


async def delete_recording(recording_id: str) -> bool:
    """Delete a recording."""
    return await doc_delete(_COLLECTION, recording_id)
