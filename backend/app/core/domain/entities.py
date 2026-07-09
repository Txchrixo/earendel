"""Core domain entities — the aggregate roots of the typed-actions engine.

These are pure Pydantic models with no IO. The infrastructure layer persists
them; modules orchestrate them. Mirrored 1:1 by src/lib/earendel/types.ts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .enums import (
    ActionStatus,
    AdapterType,
    Caller,
    ExecutionStatus,
    PermissionScope,
    PublishTarget,
    RepairStatus,
    RiskLevel,
    WorkflowCategory,
)
from .value_objects import FieldSchema


class ActionContract(BaseModel):
    """Typed contract for an action: the heart of the Web Verbs thesis."""
    inputs: list[FieldSchema]
    outputs: list[FieldSchema]
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)


class Connector(BaseModel):
    """An authorized bridge to a target app/portal the customer owns."""
    id: str
    name: str
    targetApp: str
    targetDomain: str
    workflow: str
    category: WorkflowCategory
    permission: PermissionScope
    riskLevel: RiskLevel
    allowedDomains: list[str]
    authMethod: Literal["password", "sso", "api_key", "oauth"] = "password"
    status: Literal["active", "paused", "error"] = "active"
    credentialVaultKey: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)


class CapturedStep(BaseModel):
    index: int
    type: Literal["navigate", "click", "input", "select", "download", "wait", "assert"]
    description: str
    selector: str | None = None
    url: str | None = None
    value: str | None = None
    networkCalls: int = 0
    screenshot: bool = False
    durationMs: int = 0


class Recording(BaseModel):
    id: str
    connectorId: str
    name: str
    steps: list[CapturedStep]
    totalDurationMs: int
    networkRequests: int
    domMutations: int
    screenshots: int
    harCaptured: bool = True
    status: Literal["captured", "compiling", "compiled", "failed"] = "captured"
    compiledActionId: str | None = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)


class ActionVersion(BaseModel):
    version: str
    releasedAt: datetime
    changelog: str
    adapter: AdapterType
    successRate: float
    status: Literal["stable", "latest", "deprecated", "rollback"]
    # Optional contract snapshot for version-diff (inputs/outputs at release time).
    contractSnapshot: ActionContract | None = None


class CanaryAssertion(BaseModel):
    name: str
    passed: bool


class CanaryTest(BaseModel):
    id: str
    actionId: str
    name: str
    schedule: str
    lastRun: datetime
    lastStatus: Literal["passed", "failed", "warning"]
    passRate: float
    assertions: list[CanaryAssertion]


class RepairProposal(BaseModel):
    id: str
    actionId: str
    actionVersion: str
    failedSelector: str
    candidateSelector: str
    candidateLabel: str
    confidence: float
    reason: str
    status: RepairStatus = RepairStatus.pending
    detectedAt: datetime = Field(default_factory=datetime.utcnow)
    # Repair Flywheel (Option A) — provenance + cross-client KB linkage.
    # source ∈ {"knowledge_base", "llm", "fallback"}; defaults to "fallback"
    # so legacy callers / rows without the column keep working.
    source: str = "fallback"
    # patternKey is set when the proposal is KB-sourced (so the resolve
    # endpoint can record the outcome against the right KB entry). For
    # LLM-sourced proposals that have been stored into the KB, this is
    # also populated so the resolve endpoint can update the same entry.
    patternKey: str | None = None


class TypedAction(BaseModel):
    """A compiled, versioned, risk-gated, multi-adapter business action."""
    id: str
    connectorId: str
    name: str
    signature: str
    description: str
    category: WorkflowCategory
    contract: ActionContract
    permissions: PermissionScope
    riskLevel: RiskLevel
    executionMethods: list[AdapterType]
    preferredAdapter: AdapterType
    status: ActionStatus = ActionStatus.draft
    version: str = "0.1.0"
    versions: list[ActionVersion] = Field(default_factory=list)
    testsPassed: int = 0
    testsTotal: int = 0
    canary: list[CanaryTest] = Field(default_factory=list)
    publishedAs: list[PublishTarget] = Field(default_factory=list)
    mcpToolName: str | None = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)


class TraceEvent(BaseModel):
    ts: datetime
    adapter: AdapterType
    level: Literal["info", "warn", "error"]
    message: str
    step: str | None = None
    durationMs: int | None = None


class Execution(BaseModel):
    id: str
    actionId: str
    actionName: str
    caller: Caller
    inputs: dict[str, Any]
    outputs: dict[str, Any] | None = None
    adapter: AdapterType
    fallbackChain: list[AdapterType]
    status: ExecutionStatus = ExecutionStatus.queued
    durationMs: int = 0
    startedAt: datetime = Field(default_factory=datetime.utcnow)
    finishedAt: datetime | None = None
    traces: list[TraceEvent] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    postconditionsMet: bool | None = None
    errorMessage: str | None = None
    riskApproved: bool = True
