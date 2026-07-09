"""Core domain enums — stable vocabulary shared by every module."""
from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AdapterType(str, Enum):
    """Five-tier + human fallback execution path (per NoAPI Studio research).

    Browser Use (bu_browser) is an OPTIONAL adapter inserted between the local
    browser and vision. It is NEVER the default — it activates only when:
      (a) the action's executionMethods explicitly includes `bu_browser`, AND
      (b) the local browser adapter has failed.
    This preserves Earendel's API-first moat while adding stealth / CAPTCHA /
    195-country-proxy capability for the ~5% of cases that truly need it.
    """
    api = "api"                        # 1. Official public API (default, fastest)
    internal_route = "internal_route"  # 2. Discovered internal/shadow API (APISensor-style)
    browser = "browser"                # 3. Local Playwright browser + stealth (AutoRPA-style)
    bu_browser = "bu_browser"          # 4. Browser Use Cloud (OPTIONAL — stealth + CAPTCHA + proxies)
    vision = "vision"                  # 5. OmniParser-style vision fallback
    human = "human"                    # 6. Human-in-the-loop review


class ActionStatus(str, Enum):
    draft = "draft"
    testing = "testing"
    published = "published"
    degraded = "degraded"
    broken = "broken"


class ExecutionStatus(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"
    degraded = "degraded"
    human_review = "human_review"


class PermissionScope(str, Enum):
    read_only = "read_only"
    read_write = "read_write"
    submit = "submit"
    destructive = "destructive"


class WorkflowCategory(str, Enum):
    finance = "finance"
    healthcare = "healthcare"
    logistics = "logistics"
    ecommerce = "ecommerce"
    hr = "hr"
    compliance = "compliance"
    government = "government"
    other = "other"


class PublishTarget(str, Enum):
    mcp = "mcp"
    rest = "rest"
    sdk = "sdk"
    webhook = "webhook"


class RepairStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    auto_applied = "auto_applied"


class Caller(str, Enum):
    agent = "agent"
    schedule = "schedule"
    manual = "manual"
    canary = "canary"
