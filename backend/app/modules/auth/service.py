"""Auth — service: stub session for the studio demo."""
from __future__ import annotations

from typing import Any


async def current_session() -> dict[str, Any]:
    """Return a hardcoded demo session (no real auth in this build)."""
    return {
        "user": "demo@earendel.io",
        "role": "owner",
        "teams": ["finance-ops"],
        "permissions": ["read", "write", "approve:risk:high"],
    }
