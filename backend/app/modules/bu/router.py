"""BU (Browser Use) — FastAPI router for status / provisioning / claiming.

Exposes:
  - ``GET  /api/v1/bu/status``     — is a key provisioned? masked key + last-used + claim URL.
  - ``POST /api/v1/bu/provision``  — manually trigger the signup challenge flow.
  - ``POST /api/v1/bu/claim``      — claim the key (calls BU's /cloud/signup/claim).

All endpoints sit behind the app's JWT auth middleware (the ``/api/v1`` prefix
is not in ``PUBLIC_PREFIXES``).
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from ...adapters.bu_browser_adapter import (
    _BU_API_BASE, _BU_SIGNUP_EMAIL, _BU_SIGNUP_NAME, BrowserUseAdapter,
    _solve_math_challenge,
)
from ...infrastructure.prisma_repositories import (
    bu_key_get_active, bu_key_put, bu_key_touch,
)
from ...shared.ids import new_id

router = APIRouter(prefix="/bu", tags=["bu"])

_PROVISION_TIMEOUT = 15.0


def _mask(api_key: str | None) -> str | None:
    """Mask a BU API key for safe display: ``bu_********abcd``."""
    if not api_key or len(api_key) < 8:
        return None
    return api_key[:3] + "*" * 8 + api_key[-4:]


# ---------------------------------------------------------------------------
# GET /bu/status
# ---------------------------------------------------------------------------

@router.get("/status")
async def status_endpoint() -> dict[str, Any]:
    """Return the current BU provisioning state.

    ``provisioned`` is ``True`` when an active key exists in the DB. The key
    itself is masked — never returned in plaintext.
    """
    try:
        key = await bu_key_get_active()
    except Exception as exc:
        # DB not ready — surface as not-provisioned rather than 500.
        return {
            "provisioned": False,
            "apiKeyMasked": None,
            "lastUsedAt": None,
            "claimUrl": None,
            "error": f"key lookup failed: {exc}",
        }
    if not key:
        return {
            "provisioned": False,
            "apiKeyMasked": None,
            "lastUsedAt": None,
            "claimUrl": None,
        }
    return {
        "provisioned": True,
        "apiKeyMasked": _mask(key.get("apiKey")),
        "lastUsedAt": key.get("lastUsedAt"),
        "claimUrl": key.get("claimUrl"),
    }


# ---------------------------------------------------------------------------
# POST /bu/provision
# ---------------------------------------------------------------------------

@router.post("/provision")
async def provision_endpoint() -> dict[str, Any]:
    """Manually trigger the BU signup challenge flow.

    If a key is already active, returns it without re-provisioning. Otherwise
    runs the signup → math challenge → verify flow via the adapter's helper.
    """
    try:
        existing = await bu_key_get_active()
    except Exception:
        existing = None
    if existing and existing.get("apiKey"):
        return {
            "provisioned": True,
            "apiKeyMasked": _mask(existing["apiKey"]),
            "lastUsedAt": existing.get("lastUsedAt"),
            "claimUrl": existing.get("claimUrl"),
            "message": "active key already provisioned",
        }

    # Self-provision via the adapter's helper. The adapter swallows errors;
    # here we surface them as 502s so the operator can diagnose.
    adapter = BrowserUseAdapter()
    try:
        new_key = await adapter._provision_key()  # noqa: SLF001 — internal helper reused deliberately
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"BU provisioning failed: {exc}",
        )
    return {
        "provisioned": True,
        "apiKeyMasked": _mask(new_key.get("apiKey")),
        "lastUsedAt": None,
        "claimUrl": None,
        "message": "key provisioned via challenge-response",
    }


# ---------------------------------------------------------------------------
# POST /bu/claim
# ---------------------------------------------------------------------------

@router.post("/claim")
async def claim_endpoint() -> dict[str, Any]:
    """Call BU's ``/cloud/signup/claim`` with the active key to get a claim URL.

    Stores the returned claim URL on the key row so operators can finish
    email-based ownership transfer at their leisure. Returns 409 if no key is
    provisioned.
    """
    try:
        key = await bu_key_get_active()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"key lookup failed: {exc}",
        )
    if not key or not key.get("apiKey"):
        raise HTTPException(
            status_code=409,
            detail="no BU key provisioned — POST /api/v1/bu/provision first",
        )

    try:
        async with httpx.AsyncClient(timeout=_PROVISION_TIMEOUT) as client:
            resp = await client.post(
                f"{_BU_API_BASE}/cloud/signup/claim",
                headers={
                    "X-Browser-Use-API-Key": key["apiKey"],
                    "Content-Type": "application/json",
                },
                json={"email": key.get("email") or _BU_SIGNUP_EMAIL,
                      "name": key.get("name") or _BU_SIGNUP_NAME},
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"BU claim HTTP {resp.status_code}: {resp.text[:200]}",
            )
        data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"BU claim network error: {exc}",
        )

    claim_url = (
        data.get("claim_url") or data.get("claimUrl")
        or data.get("url") or ""
    )
    if not claim_url:
        raise HTTPException(
            status_code=502,
            detail=f"BU claim returned no URL: {data!r}",
        )

    # Persist the claim URL on the key row.
    updated = dict(key)
    updated["claimUrl"] = claim_url
    updated["claimed"] = False
    await bu_key_put(updated)

    return {
        "provisioned": True,
        "apiKeyMasked": _mask(key.get("apiKey")),
        "lastUsedAt": key.get("lastUsedAt"),
        "claimUrl": claim_url,
        "message": "claim URL retrieved + stored — visit it to complete ownership",
    }
