"""Credential vault — stub that returns masked references, never secrets."""
from __future__ import annotations

from datetime import datetime
from typing import Any


class CredentialVault:
    """In-memory stub of a secrets backend (would be HashiCorp Vault in prod)."""

    _STORE: dict[str, dict[str, Any]] = {
        "acme": {"username": "ap_user@acme.com", "rotatedAt": datetime.utcnow()},
        "maersk": {"username": "logistics@acme.com", "rotatedAt": datetime.utcnow()},
        "bluecross": {"username": "billing@acme.com", "rotatedAt": datetime.utcnow()},
    }

    def get(self, key: str) -> dict[str, Any]:
        """Return masked credential ref for a connector's vault key."""
        record = self._STORE.get(key, {"rotatedAt": datetime.utcnow()})
        return {
            "masked": "••••••••",
            "rotatedAt": record.get("rotatedAt"),
            "username": record.get("username", "unknown"),
        }
