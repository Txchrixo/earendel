"""API — JWT auth middleware for FastAPI.

Verifies the backendToken JWT (minted by NextAuth) on every protected
endpoint. Public endpoints (/healthz, /readyz, /auth/*) are exempt.

The JWT is signed with BACKEND_SECRET (shared between NextAuth and FastAPI).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

BACKEND_SECRET = os.environ.get("BACKEND_SECRET", os.environ.get("NEXTAUTH_SECRET", "dev-secret-change-me"))

# Public paths that don't require authentication.
PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/healthz",
    "/api/v1/readyz",
    "/api/v1/auth/",
)

security = HTTPBearer(auto_error=False)


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any] | None:
    """Verify the JWT from the Authorization header.

    Returns the decoded payload (uid, email) if valid.
    Raises 401 if the token is missing, expired, or invalid.
    Called as a dependency on protected endpoints.

    For public endpoints, this is a no-op (returns None).
    """
    path = request.url.path

    # Public endpoints: no auth required.
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return None

    # Extract token from Authorization: Bearer <token>
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        # Also accept token from query param (for SSE/websocket fallback).
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            BACKEND_SECRET,
            algorithms=["HS256"],
            issuer="earendel-studio",
            audience="earendel-api",
        )
        # Check expiration explicitly (PyJWT does this, but double-check).
        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )


async def get_current_user(
    payload: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Extract the current user from the verified JWT payload.

    Use this as a dependency on any endpoint that needs the user identity.
    Returns {uid, email} from the JWT.
    """
    if payload is None:
        # This happens on public endpoints — return a demo user.
        return {"uid": "demo", "email": "demo@earendel.io"}
    return {"uid": payload.get("uid", ""), "email": payload.get("email", "")}
