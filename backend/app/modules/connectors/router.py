"""Connectors — FastAPI router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...core.domain.enums import PermissionScope, RiskLevel, WorkflowCategory
from . import service

router = APIRouter(prefix="/connectors", tags=["connectors"])


class CreateConnectorBody(BaseModel):
    """POST body for creating a connector."""
    name: str
    targetApp: str
    targetDomain: str
    workflow: str
    category: WorkflowCategory
    permission: PermissionScope
    riskLevel: RiskLevel
    allowedDomains: list[str] = []
    authMethod: str = "password"


@router.get("")
async def list_connectors_endpoint() -> list[dict[str, Any]]:
    """List all connectors."""
    items = await service.fetch_all()
    return [c.model_dump(mode="json") for c in items]


@router.get("/{connector_id}")
async def get_connector_endpoint(connector_id: str) -> dict[str, Any]:
    """Fetch a single connector."""
    conn = await service.fetch(connector_id)
    return conn.model_dump(mode="json")


@router.post("")
async def create_connector_endpoint(body: CreateConnectorBody) -> dict[str, Any]:
    """Create a new connector."""
    conn = await service.create_connector(
        body.name, body.targetApp, body.targetDomain, body.workflow,
        body.category, body.permission, body.riskLevel,
        body.allowedDomains, body.authMethod)
    return conn.model_dump(mode="json")
