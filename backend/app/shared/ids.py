"""Shared kernel — identifier generation."""
from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    """Prefixed, human-readable id, e.g. 'act_8f3a...'."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
