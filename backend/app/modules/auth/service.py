"""Auth - service: session, register, login (bcrypt-hashed, Prisma User table)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import bcrypt

from ...infrastructure.prisma_repositories import user_get_by_email, user_put
from ...shared.ids import new_id


def _hash_password(password: str) -> str:
    """Hash a password with bcrypt (cost 12). Returns a str for storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verify a password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


async def current_session(
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the current session.

    If a real caller (extracted from the JWT via the router) is available,
    return that user's session. Otherwise return a hardcoded demo session
    as a fallback - this is used when /auth/session is called without a
    valid JWT, since the /api/v1/auth/ prefix is exempt from the auth
    middleware.
    """
    if current_user and current_user.get("uid") and current_user.get("uid") != "demo":
        return {
            "user": current_user.get("email", "demo@earendel.io"),
            "uid": current_user["uid"],
            "role": "owner",
            "teams": [],
            "permissions": ["read", "write", "approve:risk:high"],
        }
    # Demo fallback - no authenticated user. The /auth/session endpoint is
    # public (in PUBLIC_PREFIXES) so it still works without a JWT.
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
    stored_hash = u.get("passwordHash") or ""
    # Backward-compat: legacy rows may still carry a SHA-256 hash. If the
    # value isn't a bcrypt hash ($2b$ prefix) we treat it as invalid so
    # the user must reset their password rather than silently accepting.
    if not stored_hash.startswith("$2"):
        return None
    if _verify_password(password, stored_hash):
        return {"id": u["id"], "email": u["email"], "name": u.get("name") or u["email"]}
    return None
