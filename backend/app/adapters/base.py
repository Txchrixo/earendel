"""Adapters — abstract execution backend contract.

Each adapter turns a TypedAction + inputs into an AdapterResult with
deterministic, observable telemetry. Adapters never mutate the action.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType, Caller

if TYPE_CHECKING:
    from ..infrastructure.telemetry import TraceCollector
    from ..infrastructure.vault import CredentialVault


@dataclass
class ExecutionContext:
    """Per-run context handed to every adapter (no IO hidden inside)."""
    caller: Caller
    risk_approved: bool
    run_id: str
    vault: "CredentialVault"
    telemetry: "TraceCollector"
    started_at: datetime = field(default_factory=datetime.utcnow)
    # Phase 3: screenshots captured by prior adapters (full file paths).
    # The browser adapter populates this; the vision adapter reads it.
    # Simulated screenshots (filenames that don't exist on disk) are skipped
    # by downstream adapters via an ``os.path.exists`` check.
    screenshots: list[str] = field(default_factory=list)


@dataclass
class AdapterResult:
    """Outcome of one adapter attempt — feeds the orchestrator."""
    success: bool
    outputs: dict
    traces: list[TraceEvent]
    screenshots: list[str]
    error: str | None
    durationMs: int


class ExecutionAdapter(ABC):
    """Pluggable execution backend (API, internal route, browser, vision, human)."""

    @property
    @abstractmethod
    def adapter_type(self) -> AdapterType:
        """Which AdapterType this implementation represents."""

    @abstractmethod
    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        """Run the action via this adapter; always returns (never raises)."""
