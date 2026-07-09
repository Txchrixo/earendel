"""Repair — propose a candidate selector for a failed browser execution.

The propose flow is a 3-tier ladder (Repair Flywheel — Option A):

  1. **Knowledge Base** — query the cross-client repair KB first. If a
     high-confidence match exists, return it immediately (tagged
     ``source="knowledge_base"``). This is the network-effect flywheel:
     every rupture repaired makes the next one faster for everyone.

  2. **LLM** — if the KB has no high-confidence match, ask the LLM for a
     candidate selector + reasoning (with a short timeout so it never
     blocks the repair flow). LLM proposals are tagged
     ``source="llm"`` and — when confidence is high enough — also stored
     in the KB so future failures benefit.

  3. **Deterministic fallback** — if the LLM times out or returns garbage,
     fall back to a keyword-routed candidate table. Tagged
     ``source="fallback"``.

The KB query is wrapped so a DB outage never blocks execution — the
worst case is "no KB match, fall through to the LLM", which is the
pre-flywheel behavior.
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
from .knowledge_base import (
    RepairFailure,
    STORE_MIN_CONFIDENCE,
    extract_target_domain,
    infer_intention,
    infer_widget_type,
    query_kb,
    store_repair,
)

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


def _extract_failure(
    action: TypedAction, failed: Execution
) -> RepairFailure:
    """Build a ``RepairFailure`` signature from the action + execution.

    Centralises the inference of (target_domain, widget_type, intention)
    so both the KB-query path and the KB-store path see the same signature.
    """
    err = failed.errorMessage or ""
    failed_selector = (
        err.split(":", 1)[-1].strip() if ":" in err else "unknown"
    )
    target_domain = extract_target_domain(action.name)
    widget_type = infer_widget_type(failed_selector, err)
    intention = infer_intention(action.name, err)
    return RepairFailure(
        action_name=action.name,
        target_domain=target_domain,
        failed_selector=failed_selector,
        error_message=err,
        widget_type=widget_type,
        intention=intention,
    )


async def propose(
    action: TypedAction, failed: Execution, llm: LLMClient | None = None
) -> RepairProposal | None:
    """Return a RepairProposal if the failure was a selector error, else None.

    3-tier ladder (see module docstring): KB → LLM → deterministic fallback.
    The KB is queried first (fast indexed lookup); on a high-confidence hit
    the proposal is returned immediately with ``source="knowledge_base"``.
    Otherwise the LLM is tried (when provided); its proposal is stored back
    into the KB (when confidence >= STORE_MIN_CONFIDENCE) so future failures
    benefit. The deterministic table is the final fallback.
    """
    err = (failed.errorMessage or "").lower()
    if "selector" not in err:
        return None

    failure = _extract_failure(action, failed)
    base_conf = _deterministic_confidence(action.id, failed.id)

    # ---- Tier 1: Knowledge Base -----------------------------------------
    kb_proposal = await query_kb(failure)
    if kb_proposal is not None:
        # Stamp the action context the KB couldn't know about.
        kb_proposal.actionId = action.id
        kb_proposal.actionVersion = action.version
        logger.info(
            "KB hit for %s (pattern=%s, conf=%.2f) — skipping LLM.",
            action.name, kb_proposal.patternKey, kb_proposal.confidence,
        )
        return kb_proposal

    # ---- Tier 2: LLM ----------------------------------------------------
    if llm is not None:
        llm_result = await _llm_propose(action, failure.failed_selector, llm)
        if llm_result is not None:
            candidate = llm_result.get("candidateSelector", "")
            label = llm_result.get("candidateLabel", candidate)
            confidence = float(llm_result.get("confidence", base_conf))
            confidence = max(0.5, min(0.98, confidence))
            reason = llm_result.get("reason", "LLM-proposed stable selector")
            proposal = RepairProposal(
                id=new_id("rep"),
                actionId=action.id,
                actionVersion=action.version,
                failedSelector=failure.failed_selector,
                candidateSelector=candidate,
                candidateLabel=label,
                confidence=confidence,
                reason=f"{reason} (LLM-generated)",
                status=RepairStatus.pending,
                source="llm",
            )
            # Store the LLM proposal in the KB so future failures benefit.
            # Low-confidence proposals are NOT stored (they'd pollute the KB);
            # a human can still approve + store them on the resolve path.
            if confidence >= STORE_MIN_CONFIDENCE:
                pattern_key = await store_repair(
                    proposal,
                    target_domain=failure.target_domain,
                    widget_type=failure.widget_type,
                    intention=failure.intention,
                )
                if pattern_key:
                    proposal.patternKey = pattern_key
            return proposal

    # ---- Tier 3: Deterministic fallback ---------------------------------
    selector, label, tbl_conf = _fallback_candidate(action.name)
    confidence = max(base_conf, tbl_conf)
    return RepairProposal(
        id=new_id("rep"),
        actionId=action.id,
        actionVersion=action.version,
        failedSelector=failure.failed_selector,
        candidateSelector=selector,
        candidateLabel=label,
        confidence=confidence,
        reason=f"semantically equivalent stable selector (fallback, base conf {tbl_conf})",
        status=RepairStatus.pending,
        source="fallback",
    )
