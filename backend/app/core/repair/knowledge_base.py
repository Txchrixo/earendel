"""Repair Knowledge Base — cross-client repair reuse (Option A defensive moat).

When a repair is approved (LLM or human), it is stored here so the NEXT
client hitting the same portal + widget pattern gets an instant repair.
This is the network-effect flywheel: every rupture repaired makes the
next one faster for everyone.

Public surface
--------------
- ``RepairFailure``           — lightweight failure signature dataclass.
- ``query_kb(failure)``       — semantic KB lookup (TF-IDF cosine similarity,
                                  Phase 2); returns a
  ``RepairProposal`` with ``source="knowledge_base"`` when a high-confidence
  match exists, else ``None`` (so the caller falls through to the LLM).
- ``store_repair(proposal, target_domain, widget_type, intention)`` —
  upsert an approved / LLM-proposed repair into the KB so future failures
  benefit. Best-effort — never raises.
- ``record_outcome(pattern_key, succeeded, auto_applied)`` — increment the
  KB entry's success / failure / autoApplied counters after a repair is
  resolved. Best-effort — never raises.
- ``compute_pattern_key(...)`` — deterministic key for upsert + lookup.
- ``infer_widget_type(...)``, ``infer_intention(...)``, ``extract_target_domain(...)`` —
  lightweight heuristics that turn a raw failure into the (domain, widget,
  intention) signature used by the KB.

ALL KB IO is wrapped in try/except so a DB outage never blocks the
repair flow — the worst case is "no KB match, fall through to the LLM",
which is the pre-flywheel behavior.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from ...core.domain.entities import RepairProposal
from ...core.domain.enums import RepairStatus
from ...infrastructure.prisma_repositories import (
    repair_kb_put, repair_kb_record_outcome, repair_kb_search, repair_kb_list,
)
from ...shared.ids import new_id

logger = logging.getLogger("earendel.repair_kb")

# Thresholds — a KB entry is only auto-returned when both conditions hold:
#   * confidence >= KB_MIN_CONFIDENCE  (the entry's stored confidence)
#   * success_count  >= KB_MIN_SUCCESS (real-world validation)
KB_MIN_CONFIDENCE: float = 0.85
KB_MIN_SUCCESS: int = 2

# Only LLM proposals with confidence >= STORE_MIN_CONFIDENCE are stored in
# the KB on the propose path. Lower-confidence ones can still be stored
# later if a human approves them on the resolve path.
STORE_MIN_CONFIDENCE: float = 0.70


# ---------------------------------------------------------------------------
# Failure signature
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RepairFailure:
    """Lightweight failure signature used to query the KB.

    Mirrors the fields of the KB's ``RepairKnowledge`` row that matter for
    matching: the portal (``target_domain``), the widget kind, the user
    intent, and the exact selector that broke. The action name + error
    message are kept too so the inference helpers can fall back to them.
    """

    action_name: str
    target_domain: str
    failed_selector: str
    error_message: str = ""
    widget_type: str = "unknown"
    intention: str = "generic"


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

# Action-name → portal domain. The seeded connectors map to public test APIs,
# but the repair flywheel is keyed off the *business portal* a client is
# automating (e.g. "acme.com" for an invoice portal). The mapping below
# mirrors the seeded-action → portal-domain pairings used in the seed demo
# data so failures on those workflows get KB hits out of the box.
_ACTION_DOMAIN_MAP: dict[str, str] = {
    "downloadInvoice": "acme.com",
    "trackShipment": "maersk.com",
    "checkClaimStatus": "bluecross.com",
    "downloadMarketplaceReport": "amazon.com",
    "exportNewCandidates": "linkedin.com",
    "fillSecurityQuestionnaire": "drata.com",
}


def extract_target_domain(action_name: str, connector: Any = None) -> str:
    """Best-effort inference of the portal domain for a failed action.

    Prefers the ``connector.targetDomain`` when a Connector is passed in
    (the orchestrator has it at runtime); falls back to a hardcoded
    action-name → portal map; finally returns ``"unknown"``.
    """
    if connector is not None:
        td = getattr(connector, "targetDomain", None)
        if td:
            return td
    if action_name:
        if action_name in _ACTION_DOMAIN_MAP:
            return _ACTION_DOMAIN_MAP[action_name]
        lower = action_name.lower()
        for key, domain in _ACTION_DOMAIN_MAP.items():
            if key.lower() in lower or lower in key.lower():
                return domain
    return "unknown"


def infer_widget_type(failed_selector: str, error_message: str = "") -> str:
    """Heuristic: classify the broken element from its CSS selector.

    Returns one of ``"button"``, ``"link"``, ``"input"``, ``"select"``,
    or ``"unknown"``. The error_message is consulted only when the
    selector itself is ambiguous (e.g. an empty string).
    """
    sel = (failed_selector or "").lower()
    msg = (error_message or "").lower()
    if not sel and not msg:
        return "unknown"
    # Order matters: ``input[type='submit']`` is a button, not a generic input.
    if "input[type='submit']" in sel or 'input[type="submit"]' in sel:
        return "button"
    if "button" in sel or "btn" in sel:
        return "button"
    if "a[" in sel or sel.startswith("a ") or sel.startswith("a.") or sel == "a":
        return "link"
    if "select" in sel or sel.startswith("select") or "dropdown" in msg:
        return "select"
    if "input" in sel or "textarea" in sel:
        return "input"
    if "button" in msg:
        return "button"
    if "link" in msg or "anchor" in msg:
        return "link"
    return "unknown"


def infer_intention(action_name: str, error_message: str = "") -> str:
    """Heuristic: classify the user intent of the failing action.

    Returns one of ``"download"``, ``"track"``, ``"check"``, ``"fill"``,
    ``"export"``, or ``"generic"``. The action name is the primary signal;
    the error message is consulted as a fallback (so a generic action name
    paired with a "download failed" error still resolves to ``"download"``).
    """
    name = (action_name or "").lower()
    msg = (error_message or "").lower()
    for keyword, intention in (
        ("download", "download"),
        ("track", "track"),
        ("check", "check"),
        ("fill", "fill"),
        ("export", "export"),
    ):
        if keyword in name or keyword in msg:
            return intention
    return "generic"


def compute_pattern_key(
    target_domain: str, widget_type: str, intention: str, failed_selector: str,
) -> str:
    """Deterministic key for KB upsert + lookup.

    Format: ``"{target_domain}:{widget_type}:{intention}:{failed_selector}"``.
    The failed_selector is included verbatim (NOT normalized) so two
    different broken selectors on the same portal/intention/widget produce
    two distinct KB entries — this matches how the seeded entries are keyed
    and means a single portal with multiple drifted buttons doesn't get
    collapsed into one entry.
    """
    return f"{target_domain}:{widget_type}:{intention}:{failed_selector}"


# ---------------------------------------------------------------------------
# Combined-score ranking
# ---------------------------------------------------------------------------


def _combined_score(entry: dict) -> float:
    """Rank score: ``confidence * (1 + log(1 + success)) * (1 / (1 + failure))``.

    Multiplies the LLM-confidence by a log-scaled success multiplier and a
    failure-dampening divisor. The result favors entries that are both
    high-confidence AND have been validated in production. The log on
    success_count keeps the score bounded so a 1000-success entry isn't
    infinitely preferred over a 10-success one.
    """
    confidence = float(entry.get("confidence", 0.0) or 0.0)
    success = int(entry.get("successCount", 0) or 0)
    failure = int(entry.get("failureCount", 0) or 0)
    success_mult = 1.0 + math.log1p(success)  # log1p(0) = 0 → mult = 1.0
    failure_div = 1.0 / (1.0 + failure)
    return confidence * success_mult * failure_div


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


async def query_kb(failure: RepairFailure) -> RepairProposal | None:
    """Look up a previously-approved repair for this failure signature.

    **Phase 2:** Uses TF-IDF semantic similarity (via scikit-learn) to find
    the closest KB entry, then applies the confidence/success thresholds.
    This replaces the previous exact-match SQL lookup — now a failure on
    ``button[data-invoice-download]`` can match a KB entry stored from a
    failure on ``a[aria-label='Download PDF']`` if the embedding text is
    similar enough.

    Returns a ``RepairProposal`` with ``source="knowledge_base"`` when the
    KB has a high-confidence semantic match (``confidence >=
    KB_MIN_CONFIDENCE`` AND ``success_count >= KB_MIN_SUCCESS`` AND
    ``similarity >= 0.3``). Otherwise returns ``None`` so the caller falls
    through to the LLM.

    NEVER raises — any DB / parse error is logged and swallowed so the
    repair flow always makes progress with or without the KB.
    """
    from .embedding import build_embedding_text, search_semantic, rebuild_index, get_index_version

    # Build the query embedding text from the failure signature.
    query_text = build_embedding_text(
        target_domain=failure.target_domain,
        widget_type=failure.widget_type,
        intention=failure.intention,
        failed_selector=failure.failed_selector,
        error_message=failure.error_message,
    )

    # Try semantic search first (Phase 2 — the real moat).
    semantic_results: list[tuple[dict, float]] = []
    try:
        # Ensure the index is fresh — rebuild if version changed.
        # (The index is rebuilt lazily on first call or after KB changes.)
        semantic_results = await search_semantic(
            query_text, top_k=5, min_similarity=0.3,
        )
    except Exception as exc:
        logger.warning("semantic KB search failed (%s) — falling back to SQL.", exc)

    # If semantic search found results, use the best one.
    if semantic_results:
        best, similarity = semantic_results[0]
        confidence = float(best.get("confidence", 0.0) or 0.0)
        success_count = int(best.get("successCount", 0) or 0)
        if confidence >= KB_MIN_CONFIDENCE and success_count >= KB_MIN_SUCCESS:
            pattern_key = best.get("patternKey", "") or compute_pattern_key(
                failure.target_domain, failure.widget_type, failure.intention,
                failure.failed_selector,
            )
            reason = (
                f"Cross-client repair from KB (semantic match, similarity={similarity:.2f}, "
                f"success={success_count}, confidence={confidence:.2f})"
            )
            return RepairProposal(
                id=new_id("rep"),
                actionId="",
                actionVersion="",
                failedSelector=failure.failed_selector,
                candidateSelector=best.get("repairedSelector", ""),
                candidateLabel=best.get("repairedLabel", "") or best.get("repairedSelector", ""),
                confidence=confidence,
                reason=reason,
                status=RepairStatus.pending,
                source="knowledge_base",
                patternKey=pattern_key,
            )

    # Fall back to exact-match SQL (Phase 1 behavior — for backward compat
    # and for when the TF-IDF index is empty/unavailable).
    try:
        results = await repair_kb_search(
            target_domain=failure.target_domain or None,
            widget_type=failure.widget_type or None,
            intention=failure.intention or None,
            min_confidence=0.0,
            min_success=0,
            limit=5,
        )
    except Exception as exc:
        logger.warning("KB query failed (%s) — falling through to LLM.", exc)
        return None
    if not results:
        return None

    # Rank by combined score; the DB pre-sorts by confidence+success, but
    # the combined-score ranking is the authoritative order because it
    # also penalizes failure_count.
    results.sort(key=_combined_score, reverse=True)
    best = results[0]
    confidence = float(best.get("confidence", 0.0) or 0.0)
    success_count = int(best.get("successCount", 0) or 0)
    if confidence < KB_MIN_CONFIDENCE or success_count < KB_MIN_SUCCESS:
        return None

    pattern_key = best.get("patternKey", "") or compute_pattern_key(
        failure.target_domain, failure.widget_type, failure.intention,
        failure.failed_selector,
    )
    reason = (
        f"Cross-client repair from KB (exact match, "
        f"success={success_count}, confidence={confidence:.2f})"
    )
    return RepairProposal(
        id=new_id("rep"),
        actionId="",  # filled in by the caller (propose_repair)
        actionVersion="",  # filled in by the caller
        failedSelector=failure.failed_selector,
        candidateSelector=best.get("repairedSelector", ""),
        candidateLabel=best.get("repairedLabel", "") or best.get("repairedSelector", ""),
        confidence=confidence,
        reason=reason,
        status=RepairStatus.pending,
        source="knowledge_base",
        patternKey=pattern_key,
    )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


async def store_repair(
    proposal: RepairProposal,
    target_domain: str,
    widget_type: str,
    intention: str,
) -> str | None:
    """Upsert a repair proposal into the KB so future failures benefit.

    Returns the ``patternKey`` of the stored entry on success, or ``None``
    on failure (best-effort — never raises). Existing entries are updated
    in place: their confidence / source / selector are refreshed, but
    their accumulated success / failure / autoApplied counters are
    PRESERVED (only ``record_outcome`` mutates those).
    """
    from ...infrastructure.prisma_repositories import repair_kb_get_by_pattern

    pattern_key = compute_pattern_key(
        target_domain, widget_type, intention, proposal.failedSelector,
    )

    # Phase 2: compute the embedding text for semantic retrieval.
    from .embedding import build_embedding_text, rebuild_index
    embedding_text = build_embedding_text(
        target_domain=target_domain,
        widget_type=widget_type,
        intention=intention,
        failed_selector=proposal.failedSelector,
    )

    payload: dict[str, Any] = {
        "patternKey": pattern_key,
        "targetDomain": target_domain,
        "widgetType": widget_type,
        "intention": intention,
        "failedSelector": proposal.failedSelector,
        "repairedSelector": proposal.candidateSelector,
        "repairedLabel": proposal.candidateLabel or proposal.candidateSelector,
        "confidence": float(proposal.confidence),
        "source": proposal.source or "llm",
        "status": "active",
        "embeddingText": embedding_text,
    }
    # Preserve learned counters — repair_kb_put defaults missing counts to
    # 0, which would silently zero out a learned entry on re-store. Read
    # the existing row first (best-effort: a read failure just falls back
    # to fresh 0 counts, which is still safe).
    try:
        existing = await repair_kb_get_by_pattern(pattern_key)
    except Exception as exc:
        logger.warning("KB read-before-store failed (%s) — using fresh counts.", exc)
        existing = None
    if existing:
        payload["successCount"] = int(existing.get("successCount", 0) or 0)
        payload["failureCount"] = int(existing.get("failureCount", 0) or 0)
        payload["autoAppliedCount"] = int(existing.get("autoAppliedCount", 0) or 0)
        payload["lastUsedAt"] = existing.get("lastUsedAt")
    try:
        await repair_kb_put(payload)
    except Exception as exc:
        logger.warning("KB store failed (%s) — repair not persisted to KB.", exc)
        return None

    # Phase 2: rebuild the TF-IDF index so the new entry is searchable.
    try:
        all_entries = await repair_kb_list()
        await rebuild_index(all_entries)
    except Exception as exc:
        logger.warning("KB index rebuild after store failed (%s) — index stale.", exc)

    return pattern_key


async def record_outcome(
    pattern_key: str, succeeded: bool, auto_applied: bool = False,
) -> None:
    """Record whether a KB-sourced repair succeeded or failed.

    Wraps ``repair_kb_record_outcome`` and swallows exceptions so a DB
    outage never blocks the resolve endpoint.
    """
    if not pattern_key:
        return
    try:
        await repair_kb_record_outcome(pattern_key, succeeded, auto_applied)
    except Exception as exc:
        logger.warning(
            "KB outcome recording failed for %s (%s) — ignoring.",
            pattern_key, exc,
        )
