"""Auth — service: session, register, login (demo-grade, document DB)."""
from __future__ import annotations

import hashlib
import os
from typing import Any

from ...infrastructure.database import doc_get, doc_list, doc_put
from ...shared.ids import new_id


_COLLECTION = "users"


def _hash_password(password: str) -> str:
    """Simple SHA-256 hash (demo-grade — use bcrypt in production)."""
    return hashlib.sha256(password.encode()).hexdigest()


async def current_session() -> dict[str, Any]:
    """Return a hardcoded demo session (no real auth in this build)."""
    return {
        "user": "demo@earendel.io",
        "role": "owner",
        "teams": ["finance-ops"],
        "permissions": ["read", "write", "approve:risk:high"],
    }


async def register(email: str, name: str, password: str) -> dict[str, Any] | None:
    """Register a new user. Returns None if email already exists."""
    email = email.strip().lower()
    # Check for existing user.
    existing = await doc_list(_COLLECTION)
    for u in existing:
        if u.get("email", "").lower() == email:
            return None
    user = {
        "id": new_id("usr"),
        "email": email,
        "name": name or email.split("@")[0],
        "passwordHash": _hash_password(password),
        "role": "owner",
        "createdAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    await doc_put(_COLLECTION, user["id"], user)
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


async def login(email: str, password: str) -> dict[str, Any] | None:
    """Log in an existing user. Returns None if credentials are invalid."""
    email = email.strip().lower()
    existing = await doc_list(_COLLECTION)
    for u in existing:
        if u.get("email", "").lower() == email:
            if u.get("passwordHash") == _hash_password(password):
                return {"id": u["id"], "email": u["email"], "name": u.get("name", u["email"])}
            return None
    return None
