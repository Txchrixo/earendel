"""Auth - FastAPI router: session, register, login.

Issues real HS256 JWTs (signed with BACKEND_SECRET, the same secret the
auth middleware verifies with) so tokens minted by /auth/register and
/auth/login are accepted by every protected /api/v1/* endpoint.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ...api.auth_middleware import BACKEND_SECRET
from . import service

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT parameters mirror the auth middleware (issuer/audience must match
# the values in app/api/auth_middleware.py::verify_token).
_JWT_ISSUER = "earendel-studio"
_JWT_AUDIENCE = "earendel-api"
_JWT_TTL_DAYS = 7


def _mint_jwt(user_id: str, email: str) -> str:
    """Mint a real HS256 JWT for the given user.

    Signed with BACKEND_SECRET (shared with NextAuth and the FastAPI
    auth middleware) so downstream protected endpoints accept it.
    """
    secret = os.environ.get("BACKEND_SECRET", BACKEND_SECRET)
    now = datetime.utcnow()
    payload = {
        "uid": user_id,
        "email": email,
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(days=_JWT_TTL_DAYS),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _user_from_authorization(authorization: str | None) -> dict[str, Any] | None:
    """Extract {uid, email} from a Bearer JWT, or None if absent/invalid.

    The /api/v1/auth/ prefix is exempt from the auth middleware, so we
    decode the JWT manually here to surface the real caller when one is
    present (used by /auth/session).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    try:
        payload = jwt.decode(
            token,
            BACKEND_SECRET,
            algorithms=["HS256"],
            issuer=_JWT_ISSUER,
            audience=_JWT_AUDIENCE,
        )
    except jwt.PyJWTError:
        return None
    uid = payload.get("uid")
    if not uid:
        return None
    return {"uid": uid, "email": payload.get("email", "")}


class RegisterBody(BaseModel):
    """POST body for user registration."""
    email: str
    name: str = ""
    password: str


class LoginBody(BaseModel):
    """POST body for user login."""
    email: str
    password: str


@router.get("/session")
async def session_endpoint(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return the current session.

    Public endpoint, but if a valid JWT is supplied in the Authorization
    header, returns that real user's session; otherwise falls back to a
    demo session.
    """
    current_user = _user_from_authorization(authorization)
    return await service.current_session(current_user)


@router.post("/register")
async def register_endpoint(body: RegisterBody) -> dict[str, Any]:
    """Register a new user. Stores in the document DB (bcrypt-hashed password)."""
    user = await service.register(body.email, body.name, body.password)
    if user is None:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {
        "user": user,
        "token": _mint_jwt(user["id"], user["email"]),
    }


@router.post("/login")
async def login_endpoint(body: LoginBody) -> dict[str, Any]:
    """Log in an existing user. Returns a real HS256 JWT."""
    user = await service.login(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "user": user,
        "token": _mint_jwt(user["id"], user["email"]),
    }
