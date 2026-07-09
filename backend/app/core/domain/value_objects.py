"""Core domain value objects — small immutable typed concepts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .enums import AdapterType, RiskLevel


@dataclass(frozen=True)
class FieldSchema:
    """One typed field of an action contract (input or output)."""
    name: str
    type: Literal["string", "number", "boolean", "date", "url", "enum", "file"]
    required: bool
    description: str = ""
    enum: tuple[str, ...] | None = None
    default: str | int | bool | None = None


@dataclass(frozen=True)
class AdapterPreference:
    """Risk-gated autonomy rule: which adapter may run without a human?"""
    adapter: AdapterType
    auto_run: bool           # may execute without human approval
    requires_approval: bool  # forces human confirmation before run
    log_only: bool           # always log but never mutate state


# Default risk-based execution policy (research: read-only auto, destructive gated).
RISK_POLICY: dict[RiskLevel, AdapterPreference] = {
    RiskLevel.low: AdapterPreference(AdapterType.api, True, False, False),
    RiskLevel.medium: AdapterPreference(AdapterType.internal_route, True, False, False),
    RiskLevel.high: AdapterPreference(AdapterType.browser, False, True, False),
    RiskLevel.critical: AdapterPreference(AdapterType.human, False, True, False),
}
