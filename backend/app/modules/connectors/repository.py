"""Connectors — repository (Prisma ↔ Pydantic)."""
from __future__ import annotations

from ...core.domain.entities import Connector
from ...infrastructure.prisma_repositories import (
    connector_delete, connector_get, connector_list, connector_put,
)


async def list_connectors() -> list[Connector]:
    """Return all connectors."""
    rows = await connector_list()
    return [Connector.model_validate(r) for r in rows]


async def get_connector(connector_id: str) -> Connector | None:
    """Fetch a connector by id."""
    row = await connector_get(connector_id)
    return Connector.model_validate(row) if row else None


async def put_connector(connector: Connector) -> Connector:
    """Insert or update a connector."""
    await connector_put(connector.model_dump(mode="json"))
    return connector


async def delete_connector(connector_id: str) -> bool:
    """Delete a connector; returns True if it existed."""
    return await connector_delete(connector_id)
