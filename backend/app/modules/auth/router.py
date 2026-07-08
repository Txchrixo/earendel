"""Auth — FastAPI router (stubbed session endpoint)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from . import service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/session")
async def session_endpoint() -> dict[str, Any]:
    """Return the current (demo) session."""
    return await service.current_session()
