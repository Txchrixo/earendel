"""Connectors — repository (doc-store ↔ Pydantic)."""
from __future__ import annotations

from ...core.domain.entities import Connector
from ...infrastructure.database import doc_delete, doc_get, doc_list, doc_put

_COLLECTION = "connectors"


async def list_connectors() -> list[Connector]:
    """Return all connectors."""
    rows = await doc_list(_COLLECTION)
    return [Connector.model_validate(r) for r in rows]


async def get_connector(connector_id: str) -> Connector | None:
    """Fetch a connector by id."""
    row = await doc_get(_COLLECTION, connector_id)
    return Connector.model_validate(row) if row else None


async def put_connector(connector: Connector) -> Connector:
    """Insert or update a connector."""
    await doc_put(_COLLECTION, connector.id, connector.model_dump(mode="json"))
    return connector


async def delete_connector(connector_id: str) -> bool:
    """Delete a connector; returns True if it existed."""
    return await doc_delete(_COLLECTION, connector_id)
