"""Prisma bridge — Python-side access to the Prisma SQLite database.

Since the backend is Python (FastAPI) and Prisma is Node.js, we use
SQLAlchemy directly on the same SQLite database file that Prisma manages.
The schema is identical (Prisma creates the tables, SQLAlchemy reads them).

This module provides typed repository functions that replace the old
document store (doc_put/doc_get/doc_list).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Float, Boolean, Text, select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship as sa_relationship
from sqlalchemy import ForeignKey

from ..config import DB_PATH

# The Prisma SQLite DB is at db/custom.db (project root).
# The backend's own earendel.db is for the old document store (being phased out).
_PRISMA_DB_PATH = DB_PATH.parent.parent / "db" / "custom.db"

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


# ---- Engine init ----

async def init_prisma_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        return
    _engine = create_async_engine(f"sqlite+aiosqlite:///{_PRISMA_DB_PATH}", echo=False)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def dispose_prisma_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


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
    if dt is None:
        return None
    return dt.isoformat() + "Z"


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
