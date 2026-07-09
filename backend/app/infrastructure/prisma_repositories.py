"""Prisma bridge — Python-side access to the Prisma SQLite database.

Since the backend is Python (FastAPI) and Prisma is Node.js, we use
SQLAlchemy directly on the same SQLite database file that Prisma manages.
The schema is identical (Prisma creates the tables, SQLAlchemy reads them).

This module provides typed repository functions that replace the old
document store (doc_put/doc_get/doc_list).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Float, Boolean, Text, select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship as sa_relationship
from sqlalchemy import ForeignKey

from ..config import DB_PATH

# The Prisma SQLite DB is at db/custom.db (project root).
# The backend's own earendel.db is for the old document store (being phased out).
# Allow override via env var so tests can point at an isolated test DB.
_PRISMA_DB_PATH = Path(
    os.environ.get(
        "EARENDEL_PRISMA_DB",
        str(DB_PATH.parent.parent / "db" / "custom.db"),
    )
)

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


# ---- SQLAlchemy models mirroring the Prisma schema ----

class ConnectorModel(Base):
    __tablename__ = "Connector"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    targetApp = Column(String, nullable=False)
    targetDomain = Column(String, nullable=False)
    workflow = Column(String, nullable=False)
    category = Column(String, default="other")
    permission = Column(String, default="read_only")
    riskLevel = Column(String, default="low")
    allowedDomains = Column(String, default="[]")
    authMethod = Column(String, default="password")
    status = Column(String, default="active")
    credentialVaultKey = Column(String, default="")
    userId = Column(String, ForeignKey("User.id"), nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TypedActionModel(Base):
    __tablename__ = "TypedAction"
    id = Column(String, primary_key=True)
    connectorId = Column(String, ForeignKey("Connector.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    signature = Column(String, nullable=False)
    description = Column(String, default="")
    category = Column(String, default="other")
    contract = Column(Text, default="{}")
    permissions = Column(String, default="read_only")
    riskLevel = Column(String, default="low")
    executionMethods = Column(String, default="[]")
    preferredAdapter = Column(String, default="api")
    status = Column(String, default="draft")
    version = Column(String, default="0.1.0")
    versions = Column(Text, default="[]")
    testsPassed = Column(Integer, default=0)
    testsTotal = Column(Integer, default=0)
    canary = Column(Text, default="[]")
    publishedAs = Column(String, default="[]")
    mcpToolName = Column(String, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecordingModel(Base):
    __tablename__ = "Recording"
    id = Column(String, primary_key=True)
    connectorId = Column(String, ForeignKey("Connector.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    steps = Column(Text, default="[]")
    totalDurationMs = Column(Integer, default=0)
    networkRequests = Column(Integer, default=0)
    domMutations = Column(Integer, default=0)
    screenshots = Column(Integer, default=0)
    harCaptured = Column(Boolean, default=True)
    status = Column(String, default="captured")
    compiledActionId = Column(String, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow)


class ExecutionModel(Base):
    __tablename__ = "Execution"
    id = Column(String, primary_key=True)
    actionId = Column(String, ForeignKey("TypedAction.id", ondelete="CASCADE"), nullable=False)
    actionName = Column(String, nullable=False)
    caller = Column(String, default="manual")
    inputs = Column(Text, default="{}")
    outputs = Column(Text, nullable=True)
    adapter = Column(String, default="api")
    fallbackChain = Column(String, default="[]")
    status = Column(String, default="queued")
    durationMs = Column(Integer, default=0)
    traces = Column(Text, default="[]")
    screenshots = Column(String, default="[]")
    postconditionsMet = Column(Boolean, nullable=True)
    errorMessage = Column(String, nullable=True)
    riskApproved = Column(Boolean, default=True)
    startedAt = Column(DateTime, default=datetime.utcnow)
    finishedAt = Column(DateTime, nullable=True)


class RepairProposalModel(Base):
    __tablename__ = "RepairProposal"
    id = Column(String, primary_key=True)
    actionId = Column(String, ForeignKey("TypedAction.id", ondelete="CASCADE"), nullable=False)
    actionVersion = Column(String, nullable=False)
    failedSelector = Column(String, nullable=False)
    candidateSelector = Column(String, nullable=False)
    candidateLabel = Column(String, nullable=False)
    confidence = Column(Float, default=0.8)
    reason = Column(String, default="")
    status = Column(String, default="pending")
    detectedAt = Column(DateTime, default=datetime.utcnow)
    # Repair Flywheel (Option A) — provenance + cross-client KB linkage.
    # Both columns default so legacy rows / pre-migration DBs keep working.
    source = Column(String, default="fallback")
    patternKey = Column(String, nullable=True)


class ReviewModel(Base):
    __tablename__ = "Review"
    id = Column(String, primary_key=True)
    actionId = Column(String, nullable=False)
    actionName = Column(String, nullable=False)
    actionVersion = Column(String, default="")
    caller = Column(String, default="manual")
    inputs = Column(Text, default="{}")
    prompt = Column(String, default="")
    expectedOutputs = Column(String, default="[]")
    status = Column(String, default="pending")
    reviewedBy = Column(String, nullable=True)
    reviewedAt = Column(DateTime, nullable=True)
    outputs = Column(Text, nullable=True)
    rejectReason = Column(String, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow)


class UserModel(Base):
    __tablename__ = "User"
    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    image = Column(String, nullable=True)
    emailVerified = Column(DateTime, nullable=True)
    passwordHash = Column(String, nullable=True)
    role = Column(String, default="member")
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---- Network Discovery (Option B) ----

class DiscoveredEndpointModel(Base):
    __tablename__ = "DiscoveredEndpoint"
    id = Column(String, primary_key=True)
    actionName = Column(String, nullable=False)
    connectorId = Column(String, nullable=True)
    method = Column(String, default="POST")
    url = Column(String, nullable=False)
    urlPattern = Column(String, default="")
    bodyTemplate = Column(Text, default="{}")
    headersTemplate = Column(Text, default="{}")
    cookieEnvVar = Column(String, default="")
    fieldMapping = Column(Text, default="{}")
    responseShape = Column(Text, default="{}")
    businessScore = Column(Float, default=0.0)
    clusterSize = Column(Integer, default=1)
    status = Column(String, default="active")
    staleReason = Column(String, nullable=True)
    timesReplayed = Column(Integer, default=0)
    timesSucceeded = Column(Integer, default=0)
    timesFailed = Column(Integer, default=0)
    avgLatencyMs = Column(Integer, default=0)
    discoveredFrom = Column(String, default="har")
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    lastReplayedAt = Column(DateTime, nullable=True)


# ---- Repair Flywheel (Option A) ----

class RepairKnowledgeModel(Base):
    __tablename__ = "RepairKnowledge"
    id = Column(String, primary_key=True)
    patternKey = Column(String, nullable=False, unique=True)
    targetDomain = Column(String, default="")
    widgetType = Column(String, default="button")
    intention = Column(String, default="download")
    failedSelector = Column(String, nullable=False)
    repairedSelector = Column(String, nullable=False)
    repairedLabel = Column(String, default="")
    confidence = Column(Float, default=0.85)
    source = Column(String, default="llm")
    successCount = Column(Integer, default=0)
    failureCount = Column(Integer, default=0)
    autoAppliedCount = Column(Integer, default=0)
    status = Column(String, default="active")
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    lastUsedAt = Column(DateTime, nullable=True)


# ---- Browser Use integration ----

class BrowserUseKeyModel(Base):
    __tablename__ = "BrowserUseKey"
    id = Column(String, primary_key=True)
    apiKey = Column(String, nullable=False)
    email = Column(String, nullable=True)
    name = Column(String, nullable=True)
    claimUrl = Column(String, nullable=True)
    status = Column(String, default="active")
    claimed = Column(Boolean, default=False)
    createdAt = Column(DateTime, default=datetime.utcnow)
    lastUsedAt = Column(DateTime, nullable=True)


# ---- Engine init ----

async def init_prisma_engine() -> None:
    """Initialise the SQLAlchemy async engine bound to the Prisma SQLite DB.

    Idempotently creates any missing tables (Base.metadata.create_all is a
    no-op for tables that already exist). In production, Prisma owns the
    schema; in tests, this creates the schema from the mirrored models.

    Also runs lightweight ``ALTER TABLE … ADD COLUMN`` migrations for any
    columns added to existing tables after their initial creation (e.g. the
    ``source`` + ``patternKey`` columns added to ``RepairProposal`` by the
    repair-flywheel track). The migration is idempotent — it queries
    ``PRAGMA table_info`` first and skips columns that already exist.
    """
    global _engine, _sessionmaker
    if _engine is not None:
        return
    _PRISMA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_async_engine(f"sqlite+aiosqlite:///{_PRISMA_DB_PATH}", echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def _add_missing_columns(conn) -> None:
    """Add columns added to existing tables after their initial creation.

    SQLite's ``CREATE TABLE IF NOT EXISTS`` (used by ``create_all``) is a
    no-op for tables that already exist, so newly-added ORM columns on
    pre-existing tables need an explicit ``ALTER TABLE``. Each ALTER is
    guarded by a ``PRAGMA table_info`` check so the migration is
    idempotent — running it on an already-migrated DB is a no-op.
    """
    from sqlalchemy import text

    # RepairProposal: source + patternKey (Repair Flywheel — Option A).
    try:
        cols = {row[1] for row in conn.execute(
            text("PRAGMA table_info('RepairProposal')")
        ).fetchall()}
    except Exception:
        return
    if "source" not in cols:
        try:
            conn.execute(text(
                "ALTER TABLE \"RepairProposal\" ADD COLUMN \"source\" "
                "VARCHAR DEFAULT 'fallback'"
            ))
        except Exception:
            pass
    if "patternKey" not in cols:
        try:
            conn.execute(text(
                "ALTER TABLE \"RepairProposal\" ADD COLUMN \"patternKey\" VARCHAR"
            ))
        except Exception:
            pass


async def dispose_prisma_engine() -> None:
    """Dispose the SQLAlchemy async engine + reset the sessionmaker.

    Resetting ``_sessionmaker`` to ``None`` is important: without it, the
    stale sessionmaker (bound to the disposed engine) would still satisfy
    the ``_sessionmaker is None`` guard in ``prisma_session()``, so callers
    would get a session bound to a disposed engine. For SQLite that
    happens to still work (each connection is independent), which means
    tests that don't re-initialise the engine would silently read stale
    data from the previous test's DB file. Setting ``_sessionmaker = None``
    forces ``prisma_session()`` to raise ``RuntimeError("Prisma engine not
    initialised")``, which the repair-KB wrappers catch and degrade
    gracefully from.
    """
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _sessionmaker = None


def prisma_session() -> AsyncSession:
    if _sessionmaker is None:
        raise RuntimeError("Prisma engine not initialised — call init_prisma_engine() first")
    return _sessionmaker()


# ---- JSON helpers ----

def _json_dumps(obj: Any) -> str:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return json.dumps(obj, default=str)


def _json_loads(s: str | None, default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


def _dt_to_iso(dt: datetime | None) -> str | None:
    """Convert a SQLAlchemy datetime cell to an ISO string.

    The trailing ``Z`` is intentionally NOT appended so that Pydantic parses
    the value back into a timezone-naive ``datetime`` — this matches the old
    document store behaviour and lets downstream code compare against
    ``datetime.utcnow()`` without mixing aware/naive datetimes.
    """
    if dt is None:
        return None
    return dt.isoformat()


def _iso_to_dt(s: str | None) -> datetime | None:
    """Parse an ISO string back to a naive datetime. Returns None on falsy input."""
    if not s:
        return None
    try:
        # Strip trailing Z so we get a naive datetime.
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None


# ---- Connector repository ----

async def connector_put(data: dict) -> dict:
    async with prisma_session() as s:
        existing = await s.get(ConnectorModel, data["id"])
        fields = {
            "name": data["name"],
            "targetApp": data.get("targetApp", ""),
            "targetDomain": data.get("targetDomain", ""),
            "workflow": data.get("workflow", ""),
            "category": data.get("category", "other"),
            "permission": data.get("permission", "read_only"),
            "riskLevel": data.get("riskLevel", "low"),
            "allowedDomains": _json_dumps(data.get("allowedDomains", [])),
            "authMethod": data.get("authMethod", "password"),
            "status": data.get("status", "active"),
            "credentialVaultKey": data.get("credentialVaultKey", ""),
            "updatedAt": datetime.utcnow(),
        }
        if existing is None:
            fields["id"] = data["id"]
            fields["createdAt"] = datetime.utcnow()
            s.add(ConnectorModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def connector_get(connector_id: str) -> dict | None:
    async with prisma_session() as s:
        row = await s.get(ConnectorModel, connector_id)
        if row is None:
            return None
        return _connector_to_dict(row)


async def connector_list() -> list[dict]:
    async with prisma_session() as s:
        result = await s.execute(select(ConnectorModel).order_by(ConnectorModel.createdAt))
        return [_connector_to_dict(r) for r in result.scalars()]


async def connector_delete(connector_id: str) -> bool:
    async with prisma_session() as s:
        row = await s.get(ConnectorModel, connector_id)
        if row is None:
            return False
        await s.delete(row)
        await s.commit()
        return True


def _connector_to_dict(row: ConnectorModel) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "targetApp": row.targetApp,
        "targetDomain": row.targetDomain,
        "workflow": row.workflow,
        "category": row.category,
        "permission": row.permission,
        "riskLevel": row.riskLevel,
        "allowedDomains": _json_loads(row.allowedDomains, []),
        "authMethod": row.authMethod,
        "status": row.status,
        "credentialVaultKey": row.credentialVaultKey,
        "createdAt": _dt_to_iso(row.createdAt),
        "updatedAt": _dt_to_iso(row.updatedAt),
    }


# ---- TypedAction repository ----

async def action_put(data: dict) -> dict:
    async with prisma_session() as s:
        existing = await s.get(TypedActionModel, data["id"])
        fields = {
            "connectorId": data["connectorId"],
            "name": data["name"],
            "signature": data["signature"],
            "description": data.get("description", ""),
            "category": data.get("category", "other"),
            "contract": _json_dumps(data.get("contract", {})),
            "permissions": data.get("permissions", "read_only"),
            "riskLevel": data.get("riskLevel", "low"),
            "executionMethods": _json_dumps(data.get("executionMethods", [])),
            "preferredAdapter": data.get("preferredAdapter", "api"),
            "status": data.get("status", "draft"),
            "version": data.get("version", "0.1.0"),
            "versions": _json_dumps(data.get("versions", [])),
            "testsPassed": data.get("testsPassed", 0),
            "testsTotal": data.get("testsTotal", 0),
            "canary": _json_dumps(data.get("canary", [])),
            "publishedAs": _json_dumps(data.get("publishedAs", [])),
            "mcpToolName": data.get("mcpToolName"),
            "updatedAt": datetime.utcnow(),
        }
        if existing is None:
            fields["id"] = data["id"]
            fields["createdAt"] = datetime.utcnow()
            s.add(TypedActionModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def action_get(action_id: str) -> dict | None:
    async with prisma_session() as s:
        row = await s.get(TypedActionModel, action_id)
        if row is None:
            return None
        return _action_to_dict(row)


async def action_list(connector_id: str | None = None) -> list[dict]:
    async with prisma_session() as s:
        q = select(TypedActionModel)
        if connector_id:
            q = q.where(TypedActionModel.connectorId == connector_id)
        result = await s.execute(q.order_by(TypedActionModel.createdAt))
        return [_action_to_dict(r) for r in result.scalars()]


async def action_delete(action_id: str) -> bool:
    async with prisma_session() as s:
        row = await s.get(TypedActionModel, action_id)
        if row is None:
            return False
        await s.delete(row)
        await s.commit()
        return True


def _action_to_dict(row: TypedActionModel) -> dict:
    return {
        "id": row.id,
        "connectorId": row.connectorId,
        "name": row.name,
        "signature": row.signature,
        "description": row.description,
        "category": row.category,
        "contract": _json_loads(row.contract, {}),
        "permissions": row.permissions,
        "riskLevel": row.riskLevel,
        "executionMethods": _json_loads(row.executionMethods, []),
        "preferredAdapter": row.preferredAdapter,
        "status": row.status,
        "version": row.version,
        "versions": _json_loads(row.versions, []),
        "testsPassed": row.testsPassed,
        "testsTotal": row.testsTotal,
        "canary": _json_loads(row.canary, []),
        "publishedAs": _json_loads(row.publishedAs, []),
        "mcpToolName": row.mcpToolName,
        "createdAt": _dt_to_iso(row.createdAt),
        "updatedAt": _dt_to_iso(row.updatedAt),
    }


# ---- Recording repository ----

async def recording_put(data: dict) -> dict:
    async with prisma_session() as s:
        existing = await s.get(RecordingModel, data["id"])
        fields = {
            "connectorId": data["connectorId"],
            "name": data["name"],
            "steps": _json_dumps(data.get("steps", [])),
            "totalDurationMs": data.get("totalDurationMs", 0),
            "networkRequests": data.get("networkRequests", 0),
            "domMutations": data.get("domMutations", 0),
            "screenshots": data.get("screenshots", 0),
            "harCaptured": data.get("harCaptured", True),
            "status": data.get("status", "captured"),
            "compiledActionId": data.get("compiledActionId"),
        }
        if existing is None:
            fields["id"] = data["id"]
            fields["createdAt"] = datetime.utcnow()
            s.add(RecordingModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def recording_get(recording_id: str) -> dict | None:
    async with prisma_session() as s:
        row = await s.get(RecordingModel, recording_id)
        if row is None:
            return None
        return _recording_to_dict(row)


async def recording_list() -> list[dict]:
    async with prisma_session() as s:
        result = await s.execute(select(RecordingModel).order_by(RecordingModel.createdAt))
        return [_recording_to_dict(r) for r in result.scalars()]


def _recording_to_dict(row: RecordingModel) -> dict:
    return {
        "id": row.id,
        "connectorId": row.connectorId,
        "name": row.name,
        "steps": _json_loads(row.steps, []),
        "totalDurationMs": row.totalDurationMs,
        "networkRequests": row.networkRequests,
        "domMutations": row.domMutations,
        "screenshots": row.screenshots,
        "harCaptured": row.harCaptured,
        "status": row.status,
        "compiledActionId": row.compiledActionId,
        "createdAt": _dt_to_iso(row.createdAt),
    }


# ---- Execution repository ----

async def execution_put(data: dict) -> dict:
    async with prisma_session() as s:
        existing = await s.get(ExecutionModel, data["id"])
        fields = {
            "actionId": data["actionId"],
            "actionName": data["actionName"],
            "caller": data.get("caller", "manual"),
            "inputs": _json_dumps(data.get("inputs", {})),
            "outputs": _json_dumps(data["outputs"]) if data.get("outputs") else None,
            "adapter": data.get("adapter", "api"),
            "fallbackChain": _json_dumps(data.get("fallbackChain", [])),
            "status": data.get("status", "queued"),
            "durationMs": data.get("durationMs", 0),
            "traces": _json_dumps(data.get("traces", [])),
            "screenshots": _json_dumps(data.get("screenshots", [])),
            "postconditionsMet": data.get("postconditionsMet"),
            "errorMessage": data.get("errorMessage"),
            "riskApproved": data.get("riskApproved", True),
            "startedAt": data.get("startedAt"),
            "finishedAt": data.get("finishedAt"),
        }
        # Handle datetime fields
        if isinstance(fields.get("startedAt"), str):
            fields["startedAt"] = datetime.fromisoformat(fields["startedAt"].rstrip("Z"))
        if isinstance(fields.get("finishedAt"), str):
            fields["finishedAt"] = datetime.fromisoformat(fields["finishedAt"].rstrip("Z"))
        if existing is None:
            fields["id"] = data["id"]
            if not fields.get("startedAt"):
                fields["startedAt"] = datetime.utcnow()
            s.add(ExecutionModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def execution_get(execution_id: str) -> dict | None:
    async with prisma_session() as s:
        row = await s.get(ExecutionModel, execution_id)
        if row is None:
            return None
        return _execution_to_dict(row)


async def execution_list(action_id: str | None = None) -> list[dict]:
    async with prisma_session() as s:
        q = select(ExecutionModel)
        if action_id:
            q = q.where(ExecutionModel.actionId == action_id)
        result = await s.execute(q.order_by(ExecutionModel.startedAt.desc()))
        return [_execution_to_dict(r) for r in result.scalars()]


def _execution_to_dict(row: ExecutionModel) -> dict:
    return {
        "id": row.id,
        "actionId": row.actionId,
        "actionName": row.actionName,
        "caller": row.caller,
        "inputs": _json_loads(row.inputs, {}),
        "outputs": _json_loads(row.outputs) if row.outputs else None,
        "adapter": row.adapter,
        "fallbackChain": _json_loads(row.fallbackChain, []),
        "status": row.status,
        "durationMs": row.durationMs,
        "traces": _json_loads(row.traces, []),
        "screenshots": _json_loads(row.screenshots, []),
        "postconditionsMet": row.postconditionsMet,
        "errorMessage": row.errorMessage,
        "riskApproved": row.riskApproved,
        "startedAt": _dt_to_iso(row.startedAt),
        "finishedAt": _dt_to_iso(row.finishedAt),
    }


# ---- RepairProposal repository ----

async def repair_put(data: dict) -> dict:
    async with prisma_session() as s:
        existing = await s.get(RepairProposalModel, data["id"])
        fields = {
            "actionId": data["actionId"],
            "actionVersion": data.get("actionVersion", ""),
            "failedSelector": data.get("failedSelector", ""),
            "candidateSelector": data.get("candidateSelector", ""),
            "candidateLabel": data.get("candidateLabel", ""),
            "confidence": data.get("confidence", 0.8),
            "reason": data.get("reason", ""),
            "status": data.get("status", "pending"),
            "source": data.get("source", "fallback"),
            "patternKey": data.get("patternKey"),
        }
        if existing is None:
            fields["id"] = data["id"]
            fields["detectedAt"] = datetime.utcnow()
            s.add(RepairProposalModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def repair_get(repair_id: str) -> dict | None:
    async with prisma_session() as s:
        row = await s.get(RepairProposalModel, repair_id)
        if row is None:
            return None
        return _repair_to_dict(row)


async def repair_list(action_id: str | None = None) -> list[dict]:
    async with prisma_session() as s:
        q = select(RepairProposalModel)
        if action_id:
            q = q.where(RepairProposalModel.actionId == action_id)
        result = await s.execute(q.order_by(RepairProposalModel.detectedAt.desc()))
        return [_repair_to_dict(r) for r in result.scalars()]


def _repair_to_dict(row: RepairProposalModel) -> dict:
    return {
        "id": row.id,
        "actionId": row.actionId,
        "actionVersion": row.actionVersion,
        "failedSelector": row.failedSelector,
        "candidateSelector": row.candidateSelector,
        "candidateLabel": row.candidateLabel,
        "confidence": row.confidence,
        "reason": row.reason,
        "status": row.status,
        "detectedAt": _dt_to_iso(row.detectedAt),
        "source": getattr(row, "source", None) or "fallback",
        "patternKey": getattr(row, "patternKey", None),
    }


# ---- Review repository ----

async def review_put(data: dict) -> dict:
    async with prisma_session() as s:
        existing = await s.get(ReviewModel, data["id"])
        fields = {
            "actionId": data["actionId"],
            "actionName": data.get("actionName", ""),
            "actionVersion": data.get("actionVersion", ""),
            "caller": data.get("caller", "manual"),
            "inputs": _json_dumps(data.get("inputs", {})),
            "prompt": data.get("prompt", ""),
            "expectedOutputs": _json_dumps(data.get("expectedOutputs", [])),
            "status": data.get("status", "pending"),
            "reviewedBy": data.get("reviewedBy"),
            "reviewedAt": data.get("reviewedAt"),
            "outputs": _json_dumps(data["outputs"]) if data.get("outputs") else None,
            "rejectReason": data.get("rejectReason"),
        }
        if existing is None:
            fields["id"] = data["id"]
            fields["createdAt"] = datetime.utcnow()
            s.add(ReviewModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def review_list(status: str | None = None) -> list[dict]:
    async with prisma_session() as s:
        q = select(ReviewModel)
        if status:
            q = q.where(ReviewModel.status == status)
        result = await s.execute(q.order_by(ReviewModel.createdAt.desc()))
        return [_review_to_dict(r) for r in result.scalars()]


def _review_to_dict(row: ReviewModel) -> dict:
    return {
        "id": row.id,
        "actionId": row.actionId,
        "actionName": row.actionName,
        "actionVersion": row.actionVersion,
        "caller": row.caller,
        "inputs": _json_loads(row.inputs, {}),
        "prompt": row.prompt,
        "expectedOutputs": _json_loads(row.expectedOutputs, []),
        "status": row.status,
        "reviewedBy": row.reviewedBy,
        "reviewedAt": _dt_to_iso(row.reviewedAt),
        "outputs": _json_loads(row.outputs) if row.outputs else None,
        "rejectReason": row.rejectReason,
        "createdAt": _dt_to_iso(row.createdAt),
    }


# ---- Recording delete (the only missing CRUD op used by modules) ----

async def recording_delete(recording_id: str) -> bool:
    async with prisma_session() as s:
        row = await s.get(RecordingModel, recording_id)
        if row is None:
            return False
        await s.delete(row)
        await s.commit()
        return True


# ---- User repository (auth) ----

async def user_put(data: dict) -> dict:
    """Insert or update a user row by id (email is unique)."""
    async with prisma_session() as s:
        existing = await s.get(UserModel, data["id"])
        fields = {
            "email": data["email"],
            "name": data.get("name"),
            "passwordHash": data.get("passwordHash"),
            "role": data.get("role", "member"),
            "image": data.get("image"),
            "emailVerified": data.get("emailVerified"),
            "updatedAt": datetime.utcnow(),
        }
        if isinstance(fields.get("emailVerified"), str):
            fields["emailVerified"] = datetime.fromisoformat(
                fields["emailVerified"].rstrip("Z"))
        if existing is None:
            fields["id"] = data["id"]
            fields["createdAt"] = datetime.utcnow()
            s.add(UserModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def user_get_by_email(email: str) -> dict | None:
    """Fetch a user by email (case-sensitive — callers normalise case)."""
    async with prisma_session() as s:
        result = await s.execute(
            select(UserModel).where(UserModel.email == email))
        row = result.scalars().first()
        if row is None:
            return None
        return _user_to_dict(row)


async def user_list() -> list[dict]:
    async with prisma_session() as s:
        result = await s.execute(select(UserModel).order_by(UserModel.createdAt))
        return [_user_to_dict(r) for r in result.scalars()]


def _user_to_dict(row: UserModel) -> dict:
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name,
        "image": row.image,
        "emailVerified": _dt_to_iso(row.emailVerified),
        "passwordHash": row.passwordHash,
        "role": row.role,
        "createdAt": _dt_to_iso(row.createdAt),
        "updatedAt": _dt_to_iso(row.updatedAt),
    }


# ============================================================
# DiscoveredEndpoint (Network Discovery — Option B)
# ============================================================

async def discovered_endpoint_put(data: dict) -> dict:
    """Upsert a discovered endpoint by id."""
    async with prisma_session() as s:
        existing = await s.get(DiscoveredEndpointModel, data["id"])
        fields = {
            "actionName": data.get("actionName", ""),
            "connectorId": data.get("connectorId"),
            "method": data.get("method", "POST"),
            "url": data.get("url", ""),
            "urlPattern": data.get("urlPattern", ""),
            "bodyTemplate": data.get("bodyTemplate", "{}"),
            "headersTemplate": data.get("headersTemplate", "{}"),
            "cookieEnvVar": data.get("cookieEnvVar", ""),
            "fieldMapping": data.get("fieldMapping", "{}"),
            "responseShape": data.get("responseShape", "{}"),
            "businessScore": float(data.get("businessScore", 0.0)),
            "clusterSize": int(data.get("clusterSize", 1)),
            "status": data.get("status", "active"),
            "staleReason": data.get("staleReason"),
            "timesReplayed": int(data.get("timesReplayed", 0)),
            "timesSucceeded": int(data.get("timesSucceeded", 0)),
            "timesFailed": int(data.get("timesFailed", 0)),
            "avgLatencyMs": int(data.get("avgLatencyMs", 0)),
            "discoveredFrom": data.get("discoveredFrom", "har"),
            "lastReplayedAt": _iso_to_dt(data.get("lastReplayedAt")),
            "updatedAt": datetime.utcnow(),
        }
        if existing is None:
            fields["id"] = data["id"]
            fields["createdAt"] = datetime.utcnow()
            s.add(DiscoveredEndpointModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def discovered_endpoint_list(
    action_name: str | None = None, status: str | None = None
) -> list[dict]:
    async with prisma_session() as s:
        stmt = select(DiscoveredEndpointModel)
        if action_name:
            stmt = stmt.where(DiscoveredEndpointModel.actionName == action_name)
        if status:
            stmt = stmt.where(DiscoveredEndpointModel.status == status)
        stmt = stmt.order_by(DiscoveredEndpointModel.businessScore.desc())
        result = await s.execute(stmt)
        return [_discovered_endpoint_to_dict(r) for r in result.scalars()]


async def discovered_endpoint_get(endpoint_id: str) -> dict | None:
    async with prisma_session() as s:
        row = await s.get(DiscoveredEndpointModel, endpoint_id)
        return _discovered_endpoint_to_dict(row) if row else None


async def discovered_endpoint_get_best(action_name: str) -> dict | None:
    """Return the highest-scoring active endpoint for an action."""
    async with prisma_session() as s:
        result = await s.execute(
            select(DiscoveredEndpointModel)
            .where(DiscoveredEndpointModel.actionName == action_name)
            .where(DiscoveredEndpointModel.status == "active")
            .order_by(DiscoveredEndpointModel.businessScore.desc())
            .limit(1))
        row = result.scalars().first()
        return _discovered_endpoint_to_dict(row) if row else None


async def discovered_endpoint_mark_stale(endpoint_id: str, reason: str) -> None:
    async with prisma_session() as s:
        row = await s.get(DiscoveredEndpointModel, endpoint_id)
        if row:
            row.status = "stale"
            row.staleReason = reason
            row.updatedAt = datetime.utcnow()
            await s.commit()


async def discovered_endpoint_record_replay(
    endpoint_id: str, succeeded: bool, latency_ms: int
) -> None:
    async with prisma_session() as s:
        row = await s.get(DiscoveredEndpointModel, endpoint_id)
        if row:
            row.timesReplayed += 1
            if succeeded:
                row.timesSucceeded += 1
            else:
                row.timesFailed += 1
            # Rolling average latency.
            total = row.avgLatencyMs * (row.timesReplayed - 1) + latency_ms
            row.avgLatencyMs = int(total / row.timesReplayed)
            row.lastReplayedAt = datetime.utcnow()
            row.updatedAt = datetime.utcnow()
            await s.commit()


async def discovered_endpoint_delete(endpoint_id: str) -> None:
    async with prisma_session() as s:
        row = await s.get(DiscoveredEndpointModel, endpoint_id)
        if row:
            await s.delete(row)
            await s.commit()


def _discovered_endpoint_to_dict(row: DiscoveredEndpointModel) -> dict:
    return {
        "id": row.id,
        "actionName": row.actionName,
        "connectorId": row.connectorId,
        "method": row.method,
        "url": row.url,
        "urlPattern": row.urlPattern,
        "bodyTemplate": row.bodyTemplate,
        "headersTemplate": row.headersTemplate,
        "cookieEnvVar": row.cookieEnvVar,
        "fieldMapping": row.fieldMapping,
        "responseShape": row.responseShape,
        "businessScore": row.businessScore,
        "clusterSize": row.clusterSize,
        "status": row.status,
        "staleReason": row.staleReason,
        "timesReplayed": row.timesReplayed,
        "timesSucceeded": row.timesSucceeded,
        "timesFailed": row.timesFailed,
        "avgLatencyMs": row.avgLatencyMs,
        "discoveredFrom": row.discoveredFrom,
        "createdAt": _dt_to_iso(row.createdAt),
        "updatedAt": _dt_to_iso(row.updatedAt),
        "lastReplayedAt": _dt_to_iso(row.lastReplayedAt),
    }


# ============================================================
# RepairKnowledge (Repair Flywheel — Option A)
# ============================================================

async def repair_kb_put(data: dict) -> dict:
    """Upsert a repair KB entry by patternKey."""
    async with prisma_session() as s:
        result = await s.execute(
            select(RepairKnowledgeModel).where(
                RepairKnowledgeModel.patternKey == data["patternKey"]))
        existing = result.scalars().first()
        fields = {
            "patternKey": data["patternKey"],
            "targetDomain": data.get("targetDomain", ""),
            "widgetType": data.get("widgetType", "button"),
            "intention": data.get("intention", "download"),
            "failedSelector": data.get("failedSelector", ""),
            "repairedSelector": data.get("repairedSelector", ""),
            "repairedLabel": data.get("repairedLabel", ""),
            "confidence": float(data.get("confidence", 0.85)),
            "source": data.get("source", "llm"),
            "successCount": int(data.get("successCount", 0)),
            "failureCount": int(data.get("failureCount", 0)),
            "autoAppliedCount": int(data.get("autoAppliedCount", 0)),
            "status": data.get("status", "active"),
            "lastUsedAt": _iso_to_dt(data.get("lastUsedAt")),
            "updatedAt": datetime.utcnow(),
        }
        if existing is None:
            # Auto-generate a stable, unique id from the patternKey when the
            # caller doesn't supply one. We use a short SHA-1 prefix rather
            # than a naive truncation of the patternKey, so two distinct
            # patternKeys that share a long common prefix (e.g.
            # ``acme.com:button:download:button[x]:variant-a`` and ``…:variant-b``)
            # don't collide on the id unique constraint.
            import hashlib as _hashlib
            if data.get("id"):
                fields["id"] = data["id"]
            else:
                digest = _hashlib.sha1(
                    data["patternKey"].encode("utf-8")
                ).hexdigest()[:16]
                fields["id"] = f"rkb_{digest}"
            fields["createdAt"] = datetime.utcnow()
            s.add(RepairKnowledgeModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def repair_kb_list(
    target_domain: str | None = None, status: str | None = None
) -> list[dict]:
    async with prisma_session() as s:
        stmt = select(RepairKnowledgeModel)
        if target_domain:
            stmt = stmt.where(RepairKnowledgeModel.targetDomain == target_domain)
        if status:
            stmt = stmt.where(RepairKnowledgeModel.status == status)
        stmt = stmt.order_by(RepairKnowledgeModel.successCount.desc())
        result = await s.execute(stmt)
        return [_repair_kb_to_dict(r) for r in result.scalars()]


async def repair_kb_get_by_pattern(pattern_key: str) -> dict | None:
    async with prisma_session() as s:
        result = await s.execute(
            select(RepairKnowledgeModel).where(
                RepairKnowledgeModel.patternKey == pattern_key))
        row = result.scalars().first()
        return _repair_kb_to_dict(row) if row else None


async def repair_kb_get_by_id(entry_id: str) -> dict | None:
    """Fetch a single RepairKnowledge row by its primary key id."""
    async with prisma_session() as s:
        row = await s.get(RepairKnowledgeModel, entry_id)
        return _repair_kb_to_dict(row) if row else None


async def repair_kb_set_status(entry_id: str, status: str) -> dict | None:
    """Update a RepairKnowledge row's status (e.g. ``"deprecated"``).

    Returns the updated row dict, or ``None`` if no row matches the id.
    """
    async with prisma_session() as s:
        row = await s.get(RepairKnowledgeModel, entry_id)
        if row is None:
            return None
        row.status = status
        row.updatedAt = datetime.utcnow()
        await s.commit()
        return _repair_kb_to_dict(row)


async def repair_kb_search(
    target_domain: str | None = None,
    widget_type: str | None = None,
    intention: str | None = None,
    min_confidence: float = 0.0,
    min_success: int = 0,
    limit: int = 10,
) -> list[dict]:
    """RAG-style lookup for repair patterns matching a failure signature."""
    async with prisma_session() as s:
        stmt = select(RepairKnowledgeModel).where(
            RepairKnowledgeModel.status == "active")
        if target_domain:
            stmt = stmt.where(RepairKnowledgeModel.targetDomain == target_domain)
        if widget_type:
            stmt = stmt.where(RepairKnowledgeModel.widgetType == widget_type)
        if intention:
            stmt = stmt.where(RepairKnowledgeModel.intention == intention)
        stmt = stmt.where(RepairKnowledgeModel.confidence >= min_confidence)
        stmt = stmt.where(RepairKnowledgeModel.successCount >= min_success)
        stmt = stmt.order_by(
            RepairKnowledgeModel.confidence.desc(),
            RepairKnowledgeModel.successCount.desc()).limit(limit)
        result = await s.execute(stmt)
        return [_repair_kb_to_dict(r) for r in result.scalars()]


async def repair_kb_record_outcome(
    pattern_key: str, succeeded: bool, auto_applied: bool = False
) -> None:
    """Record whether a KB-sourced repair succeeded or failed."""
    async with prisma_session() as s:
        result = await s.execute(
            select(RepairKnowledgeModel).where(
                RepairKnowledgeModel.patternKey == pattern_key))
        row = result.scalars().first()
        if row:
            if succeeded:
                row.successCount += 1
            else:
                row.failureCount += 1
            if auto_applied:
                row.autoAppliedCount += 1
            row.lastUsedAt = datetime.utcnow()
            row.updatedAt = datetime.utcnow()
            await s.commit()


def _repair_kb_to_dict(row: RepairKnowledgeModel) -> dict:
    return {
        "id": row.id,
        "patternKey": row.patternKey,
        "targetDomain": row.targetDomain,
        "widgetType": row.widgetType,
        "intention": row.intention,
        "failedSelector": row.failedSelector,
        "repairedSelector": row.repairedSelector,
        "repairedLabel": row.repairedLabel,
        "confidence": row.confidence,
        "source": row.source,
        "successCount": row.successCount,
        "failureCount": row.failureCount,
        "autoAppliedCount": row.autoAppliedCount,
        "status": row.status,
        "createdAt": _dt_to_iso(row.createdAt),
        "updatedAt": _dt_to_iso(row.updatedAt),
        "lastUsedAt": _dt_to_iso(row.lastUsedAt),
    }


# ============================================================
# BrowserUseKey (BU adapter — optional)
# ============================================================

async def bu_key_put(data: dict) -> dict:
    async with prisma_session() as s:
        existing = await s.get(BrowserUseKeyModel, data["id"])
        fields = {
            "apiKey": data.get("apiKey", ""),
            "email": data.get("email"),
            "name": data.get("name"),
            "claimUrl": data.get("claimUrl"),
            "status": data.get("status", "active"),
            "claimed": bool(data.get("claimed", False)),
            "lastUsedAt": _iso_to_dt(data.get("lastUsedAt")),
        }
        if existing is None:
            fields["id"] = data["id"]
            fields["createdAt"] = datetime.utcnow()
            s.add(BrowserUseKeyModel(**fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
        await s.commit()
    return data


async def bu_key_get_active() -> dict | None:
    """Return the single active BU API key, or None."""
    async with prisma_session() as s:
        result = await s.execute(
            select(BrowserUseKeyModel)
            .where(BrowserUseKeyModel.status == "active")
            .order_by(BrowserUseKeyModel.createdAt.desc())
            .limit(1))
        row = result.scalars().first()
        return _bu_key_to_dict(row) if row else None


async def bu_key_touch(key_id: str) -> None:
    async with prisma_session() as s:
        row = await s.get(BrowserUseKeyModel, key_id)
        if row:
            row.lastUsedAt = datetime.utcnow()
            await s.commit()


def _bu_key_to_dict(row: BrowserUseKeyModel) -> dict:
    return {
        "id": row.id,
        "apiKey": row.apiKey,
        "email": row.email,
        "name": row.name,
        "claimUrl": row.claimUrl,
        "status": row.status,
        "claimed": row.claimed,
        "createdAt": _dt_to_iso(row.createdAt),
        "lastUsedAt": _dt_to_iso(row.lastUsedAt),
    }
