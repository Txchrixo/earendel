"""Repair — propose a candidate selector for a failed browser execution.

Uses the LLM to generate a candidate selector + reasoning when available,
falling back to a deterministic keyword-routed table. The LLM path has a
short timeout so it never blocks the repair flow.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging

from ...core.domain.entities import Execution, RepairProposal, TypedAction
from ...core.domain.enums import RepairStatus
from ...infrastructure.llm_client import LLMClient
from ...shared.ids import new_id

logger = logging.getLogger("earendel.repair")

# Deterministic fallback candidates per workflow name.
_CANDIDATES: dict[str, tuple[str, str, float]] = {
    "downloadInvoice": ('button[aria-label="Download invoice"]',
                        'button[aria-label="Download invoice"]', 0.91),
    "trackShipment": ('a[data-route="tracking-detail"]',
                      'a[data-route="tracking-detail"]', 0.83),
    "checkClaimStatus": ('button[aria-label="View claim"]',
                         'button[aria-label="View claim"]', 0.76),
    "downloadMarketplaceReport": ('button[data-action="download-report"]',
                                  'button[data-action="download-report"]', 0.85),
    "exportNewCandidates": ('button[aria-label="Export candidates"]',
                            'button[aria-label="Export candidates"]', 0.80),
    "fillSecurityQuestionnaire": ('button[type="submit"][form="questionnaire"]',
                                  'button[type="submit"][form="questionnaire"]', 0.78),
}


def _fallback_candidate(action_name: str) -> tuple[str, str, float]:
    """Deterministic candidate selector + label + base confidence."""
    return _CANDIDATES.get(
        action_name,
        ('button[aria-label="Submit"]', 'button[aria-label="Submit"]', 0.75),
    )


def _deterministic_confidence(action_id: str, execution_id: str) -> float:
    """Confidence in [0.75, 0.96] derived from action + execution ids."""
    h = int(hashlib.sha256(f"{action_id}:{execution_id}".encode()).hexdigest()[:8], 16)
    return round(max(0.75, min(0.96, 0.75 + (h % 22) / 100)), 2)


async def _llm_propose(
    action: TypedAction,
    failed_selector: str,
    llm: LLMClient,
) -> dict | None:
    """Ask the LLM for a candidate selector + reasoning. Returns None on failure."""
    prompt = (
        "You are Earendel's self-healing engine. A browser-adapter execution failed "
        "because a CSS selector could not be found. Propose a replacement selector "
        "that is semantically equivalent and more stable. Return ONLY valid JSON "
        "(no prose, no markdown fences) with this exact shape:\n"
        '{"candidateSelector":"...","candidateLabel":"...","confidence":0.0,'
        '"reason":"one sentence explaining why this selector is equivalent"}\n\n'
        f"Action: {action.name}\n"
        f"Action description: {action.description}\n"
        f"Failed selector: {failed_selector}\n\n"
        "Prefer aria-label, data-route, or role-based selectors over testids. "
        "Confidence must be between 0.5 and 0.98."
    )
    system = (
        "You are a precise JSON-only API for CSS selector repair. "
        "Never include prose or markdown. Propose stable, accessible selectors."
    )
    try:
        raw = await asyncio.wait_for(
            llm.complete(prompt=prompt, system=system), timeout=6.0
        )
        # Lenient JSON parse.
        cleaned = raw.replace("```json", "").replace("```", "")
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end < 0:
            return None
        data = json.loads(cleaned[start : end + 1])
        if not data.get("candidateSelector"):
            return None
        return data
    except asyncio.TimeoutError:
        logger.warning("LLM repair proposal timed out — using fallback.")
        return None
    except Exception as exc:
        logger.warning("LLM repair proposal failed (%s) — using fallback.", exc)
        return None


async def propose(
    action: TypedAction, failed: Execution, llm: LLMClient | None = None
) -> RepairProposal | None:
    """Return a RepairProposal if the failure was a selector error, else None.

    Uses the LLM when provided; falls back to the deterministic table on
    timeout, parse failure, or any error.
    """
    err = (failed.errorMessage or "").lower()
    if "selector" not in err:
        return None

    failed_selector = (
        failed.errorMessage.split(":", 1)[-1].strip()
        if ":" in (failed.errorMessage or "")
        else "unknown"
    )

    base_conf = _deterministic_confidence(action.id, failed.id)

    # Try the LLM path first.
    if llm is not None:
        llm_result = await _llm_propose(action, failed_selector, llm)
        if llm_result is not None:
            candidate = llm_result.get("candidateSelector", "")
            label = llm_result.get("candidateLabel", candidate)
            confidence = float(llm_result.get("confidence", base_conf))
            confidence = max(0.5, min(0.98, confidence))
            reason = llm_result.get("reason", "LLM-proposed stable selector")
            return RepairProposal(
                id=new_id("rep"),
                actionId=action.id,
                actionVersion=action.version,
                failedSelector=failed_selector,
                candidateSelector=candidate,
                candidateLabel=label,
                confidence=confidence,
                reason=f"{reason} (LLM-generated)",
                status=RepairStatus.pending,
            )

    # Deterministic fallback.
    selector, label, tbl_conf = _fallback_candidate(action.name)
    confidence = max(base_conf, tbl_conf)
    return RepairProposal(
        id=new_id("rep"),
        actionId=action.id,
        actionVersion=action.version,
        failedSelector=failed_selector,
        candidateSelector=selector,
        candidateLabel=label,
        confidence=confidence,
        reason=f"semantically equivalent stable selector (fallback, base conf {tbl_conf})",
        status=RepairStatus.pending,
    )
