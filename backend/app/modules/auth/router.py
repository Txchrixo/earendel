"""Auth — FastAPI router: session, register, login."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/auth", tags=["auth"])


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
async def session_endpoint() -> dict[str, Any]:
    """Return the current (demo) session."""
    return await service.current_session()


@router.post("/register")
async def register_endpoint(body: RegisterBody) -> dict[str, Any]:
    """Register a new user. Stores in the document DB (demo-grade)."""
    user = await service.register(body.email, body.name, body.password)
    if user is None:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {"user": user, "token": f"demo-token-{user['id']}"}


@router.post("/login")
async def login_endpoint(body: LoginBody) -> dict[str, Any]:
    """Log in an existing user."""
    user = await service.login(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"user": user, "token": f"demo-token-{user['id']}"}
