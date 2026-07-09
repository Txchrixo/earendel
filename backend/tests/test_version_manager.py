"""Tests for ``app.core.versioning.version_manager`` — bump() and rollback()."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.domain.entities import ActionContract, ActionVersion, TypedAction
from app.core.domain.enums import (
    ActionStatus,
    AdapterType,
    PermissionScope,
    RiskLevel,
    WorkflowCategory,
)
from app.core.domain.value_objects import FieldSchema
from app.core.versioning.version_manager import bump, rollback


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _contract(extra_outputs: int = 0) -> ActionContract:
    """Build an invoice-shaped contract; ``extra_outputs`` adds fields."""
    outs = [
        FieldSchema("invoiceNumber", "string", True, "number"),
        FieldSchema("pdfUrl", "url", True, "pdf"),
        FieldSchema("amount", "number", True, "total"),
    ]
    for i in range(extra_outputs):
        outs.append(FieldSchema(f"extra{i}", "string", False, f"extra {i}"))
    return ActionContract(
        inputs=[FieldSchema("invoiceId", "string", True, "id")],
        outputs=outs,
        preconditions=["connector active"],
        postconditions=["pdf downloaded", "amount > 0"],
    )


def _make_action(version: str = "1.2.0") -> TypedAction:
    """Build an action at the given version with a small version history."""
    now = datetime.utcnow()
    contract = _contract()
    return TypedAction(
        id="act_test_versioning",
        connectorId="conn_test",
        name="downloadInvoice",
        signature="downloadInvoice(invoiceId: string)",
        description="test action",
        category=WorkflowCategory.finance,
        contract=contract,
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.api, AdapterType.browser],
        preferredAdapter=AdapterType.api,
        status=ActionStatus.published,
        version=version,
        versions=[
            ActionVersion(
                version="1.0.0", releasedAt=now - timedelta(days=14),
                changelog="initial compile", adapter=AdapterType.api,
                successRate=0.91, status="stable",
                contractSnapshot=_contract(),
            ),
            ActionVersion(
                version="1.1.0", releasedAt=now - timedelta(days=7),
                changelog="added retry", adapter=AdapterType.api,
                successRate=0.95, status="stable",
                contractSnapshot=_contract(),
            ),
            ActionVersion(
                version=version, releasedAt=now,
                changelog="latest", adapter=AdapterType.api,
                successRate=0.98, status="latest",
                contractSnapshot=contract,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# bump — semantic versions
# ---------------------------------------------------------------------------

def test_patch_bump_increments_patch():
    action = _make_action("1.2.0")
    bumped = bump(action, "patch", "fix a typo")
    assert bumped.version == "1.2.1"


def test_minor_bump_resets_patch():
    action = _make_action("1.2.0")
    bumped = bump(action, "minor", "add optional field")
    assert bumped.version == "1.3.0"


def test_major_bump_resets_minor_and_patch():
    action = _make_action("1.2.0")
    bumped = bump(action, "major", "breaking contract change")
    assert bumped.version == "2.0.0"


def test_bump_unknown_kind_raises_value_error():
    action = _make_action("1.2.0")
    with pytest.raises(ValueError, match="unknown bump kind"):
        bump(action, "tiny", "nope")


def test_bump_does_not_mutate_original_action():
    action = _make_action("1.2.0")
    original_version = action.version
    original_versions_len = len(action.versions)
    _ = bump(action, "patch", "fix")
    assert action.version == original_version
    assert len(action.versions) == original_versions_len


# ---------------------------------------------------------------------------
# bump — version entry + contract snapshot
# ---------------------------------------------------------------------------

def test_bump_adds_new_version_entry():
    action = _make_action("1.2.0")
    bumped = bump(action, "patch", "fix a typo")
    assert len(bumped.versions) == len(action.versions) + 1
    new_entry = bumped.versions[-1]
    assert new_entry.version == "1.2.1"
    assert new_entry.changelog == "fix a typo"
    assert new_entry.adapter == action.preferredAdapter


def test_bump_adds_contract_snapshot():
    """The new version entry must carry a contractSnapshot of the current contract."""
    action = _make_action("1.2.0")
    bumped = bump(action, "minor", "add field")
    new_entry = bumped.versions[-1]
    assert new_entry.contractSnapshot is not None
    # The snapshot must match the action's current contract (deep copy).
    assert new_entry.contractSnapshot.inputs == action.contract.inputs
    assert [o.name for o in new_entry.contractSnapshot.outputs] == \
        [o.name for o in action.contract.outputs]
    assert new_entry.contractSnapshot.postconditions == action.contract.postconditions


def test_bump_contract_snapshot_is_deep_copy():
    """Mutating the action's contract after bump must not affect the snapshot."""
    action = _make_action("1.2.0")
    bumped = bump(action, "patch", "fix")
    snapshot = bumped.versions[-1].contractSnapshot
    # Mutate the bumped action's contract.
    bumped.contract.outputs.append(FieldSchema("newf", "string", False, "new"))
    # The snapshot must be unaffected.
    assert "newf" not in [o.name for o in snapshot.outputs]


def test_bump_marks_previous_latest_as_stable():
    action = _make_action("1.2.0")
    # Before bump: the last version is "latest".
    assert action.versions[-1].status == "latest"
    bumped = bump(action, "patch", "fix")
    # After bump: the previously-latest version must be "stable".
    previously_latest = bumped.versions[-2]
    assert previously_latest.version == "1.2.0"
    assert previously_latest.status == "stable"
    # And the new entry is "latest".
    assert bumped.versions[-1].status == "latest"


def test_bump_preserves_stable_status_of_older_versions():
    action = _make_action("1.2.0")
    bumped = bump(action, "patch", "fix")
    # v1.0.0 and v1.1.0 were "stable" and must remain "stable".
    assert bumped.versions[0].status == "stable"
    assert bumped.versions[1].status == "stable"


def test_bump_updates_version_field_on_action():
    action = _make_action("1.2.0")
    bumped = bump(action, "minor", "add field")
    assert bumped.version == "1.3.0"


def test_bump_updates_updatedAt():
    action = _make_action("1.2.0")
    old_updated = action.updatedAt
    bumped = bump(action, "patch", "fix")
    assert bumped.updatedAt >= old_updated


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

def test_rollback_to_existing_version_changes_active_version():
    action = _make_action("1.2.0")
    rolled = rollback(action, "1.0.0")
    assert rolled.version == "1.0.0"


def test_rollback_appends_rollback_entry():
    action = _make_action("1.2.0")
    original_len = len(action.versions)
    rolled = rollback(action, "1.1.0")
    assert len(rolled.versions) == original_len + 1
    last = rolled.versions[-1]
    assert last.version == "1.1.0"
    assert last.status == "rollback"
    assert "rolled back" in last.changelog


def test_rollback_marks_target_as_latest():
    action = _make_action("1.2.0")
    rolled = rollback(action, "1.0.0")
    target = next(v for v in rolled.versions if v.version == "1.0.0"
                  and v.status == "latest")
    assert target is not None


def test_rollback_demotes_previous_latest_to_rollback():
    """The previously-"latest" version must NOT remain "latest" after rollback."""
    action = _make_action("1.2.0")
    rolled = rollback(action, "1.0.0")
    # Find the original v1.2.0 entry (status was "latest"); it should now be
    # "rollback" (per the rollback() implementation).
    v120_entries = [v for v in rolled.versions if v.version == "1.2.0"]
    assert any(v.status == "rollback" for v in v120_entries)
    assert not any(v.status == "latest" for v in v120_entries
                   if v is not rolled.versions[-1] or v.version != "1.0.0")


def test_rollback_to_nonexistent_version_raises():
    action = _make_action("1.2.0")
    with pytest.raises(ValueError, match="not found in action history"):
        rollback(action, "9.9.9")


def test_rollback_carries_contract_snapshot_from_target():
    action = _make_action("1.2.0")
    rolled = rollback(action, "1.1.0")
    target = next(v for v in action.versions if v.version == "1.1.0")
    new_entry = rolled.versions[-1]
    # The new rollback entry's snapshot must equal the target's snapshot.
    if target.contractSnapshot is not None:
        assert new_entry.contractSnapshot is not None
        assert (new_entry.contractSnapshot.inputs ==
                target.contractSnapshot.inputs)


def test_rollback_promotes_broken_action_to_degraded():
    """A broken action that is rolled back becomes degraded (recovery signal)."""
    action = _make_action("1.2.0")
    action.status = ActionStatus.broken
    rolled = rollback(action, "1.0.0")
    assert rolled.status == ActionStatus.degraded


def test_rollback_does_not_mutate_original_action():
    action = _make_action("1.2.0")
    original_version = action.version
    original_len = len(action.versions)
    _ = rollback(action, "1.0.0")
    assert action.version == original_version
    assert len(action.versions) == original_len
