"""Repair — apply an approved RepairProposal to a TypedAction's selectors.

Returns a new TypedAction with the selector patched and a patch-version bump.
The browser adapter reads `action.contract.preconditions` for healed selectors.
"""
from __future__ import annotations

import json

from ...core.domain.entities import TypedAction
from ...core.domain.enums import ActionStatus
from ...core.versioning.version_manager import bump


def apply(action: TypedAction, proposal) -> TypedAction:
    """Patch the action's stored selectors with the proposal's candidate."""
    healed = action.model_copy(deep=True)
    # Encode the healed selector as a precondition so the browser adapter can
    # pick it up (in a real system this would mutate a step store).
    marker = f"healed_selector:{proposal.candidateSelector}"
    if marker not in healed.contract.preconditions:
        healed.contract.preconditions = list(healed.contract.preconditions) + [marker]
    note = (
        f"repair applied: {proposal.failedSelector} → "
        f"{proposal.candidateSelector} (conf {proposal.confidence:.2f})"
    )
    return bump(healed, kind="patch", changelog=note)
