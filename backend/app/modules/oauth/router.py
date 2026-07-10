"""Phase 10 - OAuth2 Connectors.

OAuth2 PKCE flow for connectors. Instead of storing session cookies
in env vars, connectors authenticate via OAuth2:
1. User clicks "Connect with OAuth" in the frontend
2. Frontend redirects to the provider's authorize URL
3. Provider redirects back to /api/v1/oauth/callback
4. Backend exchanges the code for access + refresh tokens
5. Tokens are stored in the OAuthToken table (encrypted in production)
6. The internal_route adapter uses the access token for API replay

Supported providers (config-driven):
- Stripe (OAuth2 for Connect)
- GitHub (OAuth2 app)
- Google (OAuth2 for Gmail/Drive)
- Custom (any OAuth2 provider via config)

Academic grounding:
- OAuth 2.0 PKCE (RFC 7636) - prevents authorization code interception
- Open Banking APIs (2024) - national-scale OAuth2 marketplace governance
"""
from __future__ import annotations

import hashlib
import base64
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ...infrastructure.prisma_repositories import (
    oauth_token_put, oauth_token_get_active, oauth_token_mark_expired,
    connector_get, connector_put,
)
from ...shared.ids import new_id

router = APIRouter(prefix="/oauth", tags=["oauth"])

# --------------------------------------------------------------------------- #
# OAuth2 provider configurations
# --------------------------------------------------------------------------- #

_OAUTH_PROVIDERS: dict[str, dict[str, str]] = {
    "stripe": {
        "authorize_url": "https://connect.stripe.com/oauth/authorize",
        "token_url": "https://connect.stripe.com/oauth/token",
        "scope": "read_only",
        "client_id_env": "STRIPE_OAUTH_CLIENT_ID",
        "client_secret_env": "STRIPE_OAUTH_CLIENT_SECRET",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scope": "repo read:user",
        "client_id_env": "GITHUB_OAUTH_CLIENT_ID",
        "client_secret_env": "GITHUB_OAUTH_CLIENT_SECRET",
    },
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
    },
}


def _get_provider_config(provider: str) -> dict[str, str]:
    """Get OAuth2 config for a provider. Raises 404 if unknown."""
    config = _OAUTH_PROVIDERS.get(provider)
    if config is None:
        raise HTTPException(404, f"Unknown OAuth2 provider: {provider}")
    return config


def _get_client_credentials(config: dict[str, str]) -> tuple[str, str]:
    """Get client_id + client_secret from env vars."""
    import os
    client_id = os.environ.get(config["client_id_env"], "")
    client_secret = os.environ.get(config["client_secret_env"], "")
    if not client_id:
        raise HTTPException(
            500,
            f"OAuth2 client_id not configured (env: {config['client_id_env']})",
        )
    return client_id, client_secret


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier + code_challenge (RFC 7636)."""
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    return code_verifier, code_challenge


# --------------------------------------------------------------------------- #
# Request/Response models
# --------------------------------------------------------------------------- #

class ConnectBody(BaseModel):
    connectorId: str
    provider: str  # stripe, github, google, custom


class TokenExchangeBody(BaseModel):
    connectorId: str
    provider: str
    code: str
    codeVerifier: str | None = None


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@router.post("/connect")
async def oauth_connect(body: ConnectBody, request: Request) -> dict[str, Any]:
    """Step 1: Generate the authorize URL for the user to visit.

    The frontend redirects the user to the returned URL. After the user
    authorizes, the provider redirects back to /api/v1/oauth/callback.
    """
    config = _get_provider_config(body.provider)
    client_id, _ = _get_client_credentials(config)

    # Generate PKCE
    code_verifier, code_challenge = _generate_pkce()

    # Build the redirect URI
    redirect_uri = str(request.url_for("oauth_callback")).replace("localhost", "127.0.0.1")

    # Build authorize URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": config["scope"],
        "state": f"{body.connectorId}:{body.provider}",
    }
    # Add PKCE for providers that support it
    if body.provider in ("github", "google"):
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    authorize_url = f"{config['authorize_url']}?{urlencode(params)}"

    return {
        "authorizeUrl": authorize_url,
        "codeVerifier": code_verifier,
        "redirectUri": redirect_uri,
        "state": params["state"],
    }


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
) -> dict[str, Any]:
    """Step 2: OAuth2 callback endpoint.

    The provider redirects here with the authorization code. We exchange
    it for access + refresh tokens and store them.
    """
    if error:
        raise HTTPException(400, f"OAuth2 provider returned error: {error}")

    # Parse state (connectorId:provider)
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(400, f"Invalid state: {state}")
    connector_id, provider = parts

    config = _get_provider_config(provider)
    client_id, client_secret = _get_client_credentials(config)

    redirect_uri = str(request.url_for("oauth_callback")).replace("localhost", "127.0.0.1")

    # Exchange code for tokens
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            config["token_url"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
        )

    if token_resp.status_code >= 400:
        raise HTTPException(
            400,
            f"Token exchange failed: HTTP {token_resp.status_code} - {token_resp.text[:200]}",
        )

    token_data = token_resp.json()
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token")
    token_type = token_data.get("token_type", "Bearer")
    expires_in = token_data.get("expires_in")
    scope = token_data.get("scope", "")

    if not access_token:
        raise HTTPException(400, "Token exchange returned no access_token")

    # Compute expiry
    from datetime import datetime, timedelta
    expires_at = None
    if expires_in:
        expires_at = (datetime.utcnow() + timedelta(seconds=int(expires_in))).isoformat() + "Z"

    # Store the token
    token_record = {
        "id": new_id("oaut"),
        "connectorId": connector_id,
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": token_type,
        "expiresAt": expires_at,
        "scope": scope,
        "status": "active",
    }
    await oauth_token_put(token_record)

    # Update the connector's authMethod to oauth
    connector = await connector_get(connector_id)
    if connector:
        connector["authMethod"] = "oauth"
        await connector_put(connector)

    return {
        "status": "connected",
        "connectorId": connector_id,
        "provider": provider,
        "tokenType": token_type,
        "scope": scope,
        "expiresAt": expires_at,
    }


@router.post("/exchange")
async def oauth_exchange(body: TokenExchangeBody) -> dict[str, Any]:
    """Alternative to callback: exchange code directly (for SPAs without
    a backend callback URL)."""
    config = _get_provider_config(body.provider)
    client_id, client_secret = _get_client_credentials(config)

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            config["token_url"],
            data={
                "grant_type": "authorization_code",
                "code": body.code,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": body.codeVerifier or "",
            },
            headers={"Accept": "application/json"},
        )

    if token_resp.status_code >= 400:
        raise HTTPException(400, f"Token exchange failed: {token_resp.text[:200]}")

    token_data = token_resp.json()
    access_token = token_data.get("access_token", "")
    if not access_token:
        raise HTTPException(400, "No access_token in response")

    from datetime import datetime, timedelta
    expires_at = None
    if token_data.get("expires_in"):
        expires_at = (datetime.utcnow() + timedelta(seconds=int(token_data["expires_in"]))).isoformat() + "Z"

    token_record = {
        "id": new_id("oaut"),
        "connectorId": body.connectorId,
        "accessToken": access_token,
        "refreshToken": token_data.get("refresh_token"),
        "tokenType": token_data.get("token_type", "Bearer"),
        "expiresAt": expires_at,
        "scope": token_data.get("scope", ""),
        "status": "active",
    }
    await oauth_token_put(token_record)

    # Update connector authMethod
    connector = await connector_get(body.connectorId)
    if connector:
        connector["authMethod"] = "oauth"
        await connector_put(connector)

    return {"status": "connected", "connectorId": body.connectorId, "expiresAt": expires_at}


@router.get("/status/{connector_id}")
async def oauth_status(connector_id: str) -> dict[str, Any]:
    """Check the OAuth2 token status for a connector."""
    token = await oauth_token_get_active(connector_id)
    if token is None:
        return {"connected": False, "connectorId": connector_id}
    return {
        "connected": True,
        "connectorId": connector_id,
        "tokenType": token["tokenType"],
        "scope": token["scope"],
        "expiresAt": token["expiresAt"],
        "status": token["status"],
    }


@router.post("/disconnect/{connector_id}")
async def oauth_disconnect(connector_id: str) -> dict[str, Any]:
    """Disconnect OAuth2 for a connector (marks tokens as expired)."""
    await oauth_token_mark_expired(connector_id)

    # Update connector authMethod back to password
    connector = await connector_get(connector_id)
    if connector:
        connector["authMethod"] = "password"
        await connector_put(connector)

    return {"status": "disconnected", "connectorId": connector_id}


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    """List supported OAuth2 providers."""
    import os
    providers = []
    for name, config in _OAUTH_PROVIDERS.items():
        client_id_env = config["client_id_env"]
        configured = bool(os.environ.get(client_id_env))
        providers.append({
            "name": name,
            "scope": config["scope"],
            "configured": configured,
        })
    return {"providers": providers}
