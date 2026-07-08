"""LLM client — deterministic local stub, no network.

Routes by keyword in the prompt to a canned but contextual response. Used by
the schema compiler (recording → contract) and the repair proposer
(failed selector → candidate selector).
"""
from __future__ import annotations

import json
import re


class LLMClient:
    """Deterministic local LLM stub for compile / repair / classify prompts."""

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Return a canned response based on keywords in the prompt."""
        p = prompt.lower()
        if "compile" in p or "contract" in p:
            return self._contract_response(prompt)
        if "repair" in p or "selector" in p:
            return self._repair_response(prompt)
        if "classify" in p or "risk" in p:
            return json.dumps({"risk": "low", "category": "finance"})
        return "ack"

    def _contract_response(self, prompt: str) -> str:
        name_match = re.search(r"name\s*[:=]\s*['\"]?(\w+)", prompt, re.I)
        name = name_match.group(1) if name_match else "compiledAction"
        return json.dumps({
            "name": name,
            "description": f"Compiled action for {name}",
            "inputs": [{"name": "id", "type": "string", "required": True,
                        "description": "Primary key"}],
            "outputs": [
                {"name": "status", "type": "string", "required": True,
                 "description": "Outcome status"},
                {"name": "pdfUrl", "type": "url", "required": False,
                 "description": "Generated artifact URL"},
            ],
            "preconditions": ["connector active"],
            "postconditions": ["status present"],
        })

    def _repair_response(self, prompt: str) -> str:
        sel_match = re.search(r"selector[^:]*[:=]\s*['\"]([^'\"]+)", prompt, re.I)
        failed = sel_match.group(1) if sel_match else 'button[data-testid="x"]'
        return json.dumps({
            "candidateSelector": 'button[aria-label="Download invoice"]',
            "candidateLabel": 'button[aria-label="Download invoice"]',
            "confidence": 0.88,
            "reason": f"semantically equivalent stable label for {failed}",
        })
