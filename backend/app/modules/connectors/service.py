"""Connectors — service: business rules for managing Connector aggregates."""
from __future__ import annotations

from datetime import datetime

from ...core.domain.entities import Connector
from ...core.domain.enums import PermissionScope, RiskLevel
from ...shared.errors import ValidationError
from ...shared.ids import new_id
from .repository import get_connector, list_connectors, put_connector


def _validate(permission: PermissionScope, risk: RiskLevel) -> None:
    """Business rule: destructive + critical is not allowed."""
    if permission == PermissionScope.destructive and risk == RiskLevel.critical:
        raise ValidationError("destructive permission cannot be combined with critical risk")


async def create_connector(
    name: str, target_app: str, target_domain: str, workflow: str,
    category, permission: PermissionScope, risk: RiskLevel,
    allowed_domains: list[str], auth_method: str = "password",
) -> Connector:
    """Create and persist a new Connector."""
    _validate(permission, risk)
    conn = Connector(
        id=new_id("conn"), name=name, targetApp=target_app,
        targetDomain=target_domain, workflow=workflow, category=category,
        permission=permission, riskLevel=risk, allowedDomains=allowed_domains,
        authMethod=auth_method, credentialVaultKey=target_domain.split(".")[0],
        createdAt=datetime.utcnow(), updatedAt=datetime.utcnow(),
    )
    return await put_connector(conn)


async def fetch(connector_id: str) -> Connector:
    """Fetch a connector or raise NotFoundError."""
    from ...shared.errors import NotFoundError
    conn = await get_connector(connector_id)
    if conn is None:
        raise NotFoundError("Connector", connector_id)
    return conn


async def fetch_all() -> list[Connector]:
    """Return all connectors."""
    return await list_connectors()
