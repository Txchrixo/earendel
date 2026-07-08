"""Infrastructure — async SQLite document store.

Earendel stores each aggregate root (Connector, Recording, TypedAction,
Execution, RepairProposal) as a JSON document keyed by id with a collection
discriminator. This keeps the Pydantic domain models pure (no ORM mapping
ceremony) and the repositories tiny.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Index, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import DB_PATH, settings

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    collection = Column(String(64), primary_key=True, index=True)
    id = Column(String(64), primary_key=True, index=True)
    payload = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_doc_collection", "collection"),)


async def init_engine() -> None:
    global _engine, _sessionmaker
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_async_engine(settings.database_url, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def session() -> AsyncSession:
    if _sessionmaker is None:
        raise RuntimeError("DB engine not initialised — call init_engine() first")
    return _sessionmaker()


# ---- Document repository helpers (used by module repositories) ----

async def doc_put(collection: str, id_: str, payload: dict[str, Any]) -> None:
    async with session() as s:
        existing = await s.get(Document, (collection, id_))
        text = json.dumps(payload, default=_json_default)
        if existing is None:
            s.add(Document(collection=collection, id=id_, payload=text))
        else:
            existing.payload = text
            existing.updated_at = datetime.utcnow()
        await s.commit()


async def doc_get(collection: str, id_: str) -> dict[str, Any] | None:
    async with session() as s:
        row = await s.get(Document, (collection, id_))
        if row is None:
            return None
        return json.loads(row.payload)


async def doc_list(collection: str) -> list[dict[str, Any]]:
    async with session() as s:
        result = await s.execute(
            select(Document).where(Document.collection == collection)
        )
        return [json.loads(r.payload) for r in result.scalars().all()]


async def doc_delete(collection: str, id_: str) -> bool:
    async with session() as s:
        row = await s.get(Document, (collection, id_))
        if row is None:
            return False
        await s.delete(row)
        await s.commit()
        return True


async def doc_all() -> list[tuple[str, str, dict[str, Any]]]:
    """Return every document — used by seed + diagnostics."""
    async with session() as s:
        result = await s.execute(select(Document))
        return [
            (r.collection, r.id, json.loads(r.payload))
            for r in result.scalars().all()
        ]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)
