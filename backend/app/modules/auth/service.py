"""Auth — service: session, register, login (demo-grade, Prisma User table)."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from ...infrastructure.prisma_repositories import user_get_by_email, user_put
from ...shared.ids import new_id


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
    # Check for existing user by email (Prisma User.email is unique).
    existing = await user_get_by_email(email)
    if existing is not None:
        return None
    user = {
        "id": new_id("usr"),
        "email": email,
        "name": name or email.split("@")[0],
        "passwordHash": _hash_password(password),
        "role": "owner",
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }
    await user_put(user)
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


async def login(email: str, password: str) -> dict[str, Any] | None:
    """Log in an existing user. Returns None if credentials are invalid."""
    email = email.strip().lower()
    u = await user_get_by_email(email)
    if u is None:
        return None
    if u.get("passwordHash") == _hash_password(password):
        return {"id": u["id"], "email": u["email"], "name": u.get("name") or u["email"]}
    return None
