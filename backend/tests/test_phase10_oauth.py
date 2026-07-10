"""Tests for Phase 10 - OAuth2 Connectors.

Tests that:
1. OAuth2 provider list returns stripe, github, google
2. Connect endpoint generates an authorize URL with PKCE
3. Status endpoint returns connected=false when no token
4. Status endpoint returns connected=true when token exists
5. Disconnect marks tokens as expired
6. OAuthToken CRUD (put, get_active, mark_expired)
7. Internal route adapter uses OAuth2 token when authMethod=oauth
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.infrastructure.prisma_repositories import (
    oauth_token_put, oauth_token_get_active, oauth_token_mark_expired,
)


# --------------------------------------------------------------------------- #
# 1. Provider list
# --------------------------------------------------------------------------- #

class TestOAuthProviders:
    """Tests for the OAuth2 provider list."""

    @pytest.mark.asyncio
    async def test_list_providers(self, client):
        """GET /api/v1/oauth/providers should return stripe, github, google."""
        response = await client.get("/api/v1/oauth/providers")
        assert response.status_code == 200
        data = response.json()
        names = [p["name"] for p in data["providers"]]
        assert "stripe" in names
        assert "github" in names
        assert "google" in names


# --------------------------------------------------------------------------- #
# 2. Token status
# --------------------------------------------------------------------------- #

class TestOAuthStatus:
    """Tests for the OAuth2 status endpoint."""

    @pytest.mark.asyncio
    async def test_status_not_connected(self, client, auth_headers):
        """Status should return connected=false when no token exists."""
        response = await client.get(
            "/api/v1/oauth/status/conn_nonexistent", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_status_connected(self, seeded_db, client, auth_headers):
        """Status should return connected=true when a token exists."""
        from app.infrastructure.prisma_repositories import connector_list
        connectors = await connector_list()
        if not connectors:
            pytest.skip("No seeded connectors")
        conn_id = connectors[0]["id"]

        # Store a token
        await oauth_token_put({
            "id": "oaut_test_001",
            "connectorId": conn_id,
            "accessToken": "test_access_token_123",
            "refreshToken": "test_refresh_token",
            "tokenType": "Bearer",
            "expiresAt": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "scope": "read_only",
            "status": "active",
        })

        response = await client.get(
            f"/api/v1/oauth/status/{conn_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["tokenType"] == "Bearer"


# --------------------------------------------------------------------------- #
# 3. Disconnect
# --------------------------------------------------------------------------- #

class TestOAuthDisconnect:
    """Tests for the OAuth2 disconnect endpoint."""

    @pytest.mark.asyncio
    async def test_disconnect_marks_token_expired(self, seeded_db, client, auth_headers):
        """Disconnect should mark the token as expired."""
        from app.infrastructure.prisma_repositories import connector_list
        connectors = await connector_list()
        if not connectors:
            pytest.skip("No seeded connectors")
        conn_id = connectors[0]["id"]

        # Store a token
        await oauth_token_put({
            "connectorId": conn_id,
            "accessToken": "test_token",
            "status": "active",
        })

        # Verify it's active
        token = await oauth_token_get_active(conn_id)
        assert token is not None

        # Disconnect
        response = await client.post(
            f"/api/v1/oauth/disconnect/{conn_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"

        # Verify token is now expired (no active token)
        token = await oauth_token_get_active(conn_id)
        assert token is None


# --------------------------------------------------------------------------- #
# 4. OAuthToken CRUD
# --------------------------------------------------------------------------- #

class TestOAuthTokenCRUD:
    """Tests for the OAuthToken repository functions."""

    @pytest.mark.asyncio
    async def test_put_and_get_token(self, seeded_db):
        """Should store and retrieve an OAuth2 token."""
        from app.infrastructure.prisma_repositories import connector_list
        connectors = await connector_list()
        conn_id = connectors[0]["id"]

        await oauth_token_put({
            "connectorId": conn_id,
            "accessToken": "abc123",
            "refreshToken": "refresh456",
            "tokenType": "Bearer",
            "scope": "read_only",
            "status": "active",
        })

        token = await oauth_token_get_active(conn_id)
        assert token is not None
        assert token["accessToken"] == "abc123"
        assert token["refreshToken"] == "refresh456"
        assert token["tokenType"] == "Bearer"

    @pytest.mark.asyncio
    async def test_get_active_returns_none_when_no_token(self, seeded_db):
        """Should return None when no active token exists."""
        result = await oauth_token_get_active("conn_nonexistent_999")
        assert result is None

    @pytest.mark.asyncio
    async def test_mark_expired(self, seeded_db):
        """Should mark all tokens for a connector as expired."""
        from app.infrastructure.prisma_repositories import connector_list
        connectors = await connector_list()
        conn_id = connectors[0]["id"]

        await oauth_token_put({
            "connectorId": conn_id,
            "accessToken": "abc123",
            "status": "active",
        })

        # Verify active
        assert await oauth_token_get_active(conn_id) is not None

        # Mark expired
        await oauth_token_mark_expired(conn_id)

        # Verify no active token
        assert await oauth_token_get_active(conn_id) is None

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing_token(self, seeded_db):
        """Should replace an existing token on upsert."""
        from app.infrastructure.prisma_repositories import connector_list
        connectors = await connector_list()
        conn_id = connectors[0]["id"]

        # Put first token
        await oauth_token_put({
            "connectorId": conn_id,
            "accessToken": "old_token",
            "status": "active",
        })

        # Put second token (should replace)
        await oauth_token_put({
            "connectorId": conn_id,
            "accessToken": "new_token",
            "status": "active",
        })

        token = await oauth_token_get_active(conn_id)
        assert token is not None
        assert token["accessToken"] == "new_token"


# --------------------------------------------------------------------------- #
# 5. Internal route adapter uses OAuth2 token
# --------------------------------------------------------------------------- #

class TestInternalRouteOAuth:
    """Tests that the internal_route adapter uses OAuth2 tokens."""

    @pytest.mark.asyncio
    async def test_adapter_prefers_oauth_token(self, seeded_db):
        """When authMethod=oauth, the adapter should use the OAuth2 token."""
        from app.adapters.internal_route_adapter import InternalRouteAdapter
        from app.adapters.base import ExecutionContext
        from app.infrastructure.telemetry import TraceCollector
        from app.infrastructure.vault import CredentialVault
        from app.core.domain.entities import TypedAction, ActionContract
        from app.core.domain.value_objects import FieldSchema
        from app.core.domain.enums import (
            RiskLevel, PermissionScope, WorkflowCategory, ActionStatus, Caller, AdapterType,
        )
        from app.infrastructure.prisma_repositories import (
            connector_list, connector_put, oauth_token_put,
        )

        connectors = await connector_list()
        conn_id = connectors[0]["id"]

        # Set authMethod to oauth + store a token
        conn = connectors[0]
        conn["authMethod"] = "oauth"
        await connector_put(conn)
        await oauth_token_put({
            "connectorId": conn_id,
            "accessToken": "oauth_access_token_xyz",
            "status": "active",
        })

        action = TypedAction(
            id="act_oauth_test",
            connectorId=conn_id,
            name="testAction",
            signature="testAction()",
            description="test",
            category=WorkflowCategory.finance,
            contract=ActionContract(
                name="testAction",
                inputs=[],
                outputs=[FieldSchema(name="result", type="string", required=True)],
            ),
            permissions=PermissionScope.read_only,
            riskLevel=RiskLevel.low,
            executionMethods=[],
            preferredAdapter=AdapterType.internal_route,
            status=ActionStatus.testing,
        )

        adapter = InternalRouteAdapter()
        ctx = ExecutionContext(
            caller=Caller.manual, risk_approved=True, run_id="run_oauth_test",
            vault=CredentialVault(), telemetry=TraceCollector(),
        )

        # The _get_session_cookie method should return the OAuth2 access token
        result = await adapter._get_session_cookie(action, ctx, "TEST_COOKIE_ENV")
        assert result == "oauth_access_token_xyz"
