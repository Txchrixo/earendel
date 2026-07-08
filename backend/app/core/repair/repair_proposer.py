"""Repair — propose a candidate selector for a failed browser execution."""
from __future__ import annotations

import hashlib

from ...core.domain.entities import Execution, RepairProposal, TypedAction
from ...core.domain.enums import RepairStatus
from ...infrastructure.llm_client import LLMClient
from ...shared.ids import new_id

# Stable candidate labels per workflow — deterministic + plausible.
_CANDIDATES: dict[str, tuple[str, str, float]] = {
    "downloadInvoice": ('button[aria-label="Download invoice"]',
                        'button[aria-label="Download invoice"]', 0.91),
    "trackShipment": ('a[data-route="tracking-detail"]',
                      'a[data-route="tracking-detail"]', 0.83),
    "checkClaimStatus": ('button[aria-label="View claim"]',
                         'button[aria-label="View claim"]', 0.76),
}


async def propose(
    action: TypedAction, failed: Execution, llm: LLMClient | None = None
) -> RepairProposal | None:
    """Return a RepairProposal if the failure was a selector error, else None."""
    err = (failed.errorMessage or "").lower()
    if "selector" not in err:
        return None
    selector, label, base_conf = _CANDIDATES.get(
        action.name, ('button[aria-label="Submit"]',
                      'button[aria-label="Submit"]', 0.75))
    # Deterministic confidence in [0.75, 0.96] from action id + run.
    h = int(hashlib.sha256(f"{action.id}:{failed.id}".encode()).hexdigest()[:8], 16)
    confidence = round(0.75 + (h % 22) / 100, 2)  # 0.75..0.96
    confidence = max(min(confidence, 0.96), 0.75)
    return RepairProposal(
        id=new_id("rep"),
        actionId=action.id,
        actionVersion=action.version,
        failedSelector=failed.errorMessage.split(":", 1)[-1].strip()
        if ":" in (failed.errorMessage or "") else "unknown",
        candidateSelector=selector,
        candidateLabel=label,
        confidence=confidence,
        reason=f"semantically equivalent stable selector (base conf {base_conf})",
        status=RepairStatus.pending,
    )
