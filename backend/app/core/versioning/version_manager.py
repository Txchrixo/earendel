"""Versioning — semantic bump + rollback for TypedActions."""
from __future__ import annotations

from datetime import datetime

from ...core.domain.entities import ActionVersion, TypedAction
from ...core.domain.enums import ActionStatus


def _split(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    while len(parts) < 3:
        parts.append("0")
    return tuple(int(p) for p in parts[:3])  # type: ignore[return-value]


def _join(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def bump(action: TypedAction, kind: str, changelog: str) -> TypedAction:
    """Return a copy of `action` with version bumped and a new version entry.

    The new version entry carries a contractSnapshot of the current contract so
    the version-diff view can show how inputs/outputs evolved over time.
    """
    major, minor, patch = _split(action.version)
    if kind == "patch":
        patch += 1
    elif kind == "minor":
        minor, patch = minor + 1, 0
    elif kind == "major":
        major, minor, patch = major + 1, 0, 0
    else:
        raise ValueError(f"unknown bump kind: {kind}")
    new_version = _join(major, minor, patch)
    new_entry = ActionVersion(
        version=new_version,
        releasedAt=datetime.utcnow(),
        changelog=changelog,
        adapter=action.preferredAdapter,
        successRate=0.97,
        status="latest",
        contractSnapshot=action.contract.model_copy(deep=True),
    )
    updated = action.model_copy(deep=True)
    updated.versions = [
        ActionVersion(**{**v.model_dump(), "status":
                         "stable" if v.status == "latest" else v.status})
        for v in updated.versions
    ] + [new_entry]
    updated.version = new_version
    updated.updatedAt = datetime.utcnow()
    return updated


def rollback(action: TypedAction, version: str) -> TypedAction:
    """Roll back the active version of `action` to a previously released one.

    The rollback entry carries a contractSnapshot of the target version's
    contract (if it had one) so the diff remains accurate.
    """
    updated = action.model_copy(deep=True)
    if not any(v.version == version for v in updated.versions):
        raise ValueError(f"version {version} not found in action history")
    target = next(v for v in updated.versions if v.version == version)
    updated.versions = [
        ActionVersion(**{**v.model_dump(), "status":
                         "latest" if v.version == version else
                         ("rollback" if v.status == "latest" else v.status)})
        for v in updated.versions
    ]
    updated.versions.append(ActionVersion(
        version=version, releasedAt=datetime.utcnow(),
        changelog=f"rolled back to {version}", adapter=action.preferredAdapter,
        successRate=0.95, status="rollback",
        contractSnapshot=target.contractSnapshot,
    ))
    updated.version = version
    updated.updatedAt = datetime.utcnow()
    if updated.status == ActionStatus.broken:
        updated.status = ActionStatus.degraded
    return updated
