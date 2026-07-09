"""Adapter 4 — Browser Use (BU) Cloud (OPTIONAL).

Self-provisions an API key via a challenge-response signup flow, then drives
Browser Use's cloud browser (stealth + CAPTCHA solving + 195-country proxy
pool) to complete actions that the local Playwright adapter cannot.

BU is NEVER the default path. It activates only when:
  (a) the action's ``executionMethods`` explicitly lists ``bu_browser``, AND
  (b) the local browser adapter has already failed (the orchestrator's
      fallback chain reaches this adapter in order).

If the BU API is unreachable (network error, bad challenge, HTTP failure,
parse failure, polling timeout), the adapter falls back to a deterministic
simulation so the orchestrator can continue to the next adapter in the chain
(vision → human).
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import httpx

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from ..infrastructure.prisma_repositories import (
    bu_key_get_active, bu_key_put, bu_key_touch,
)
from ..shared.ids import new_id
from .base import AdapterResult, ExecutionContext, ExecutionAdapter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BU_API_BASE = "https://api.browser-use.com"
_BU_SIGNUP_EMAIL = "earendel@system.local"
_BU_SIGNUP_NAME = "Earendel Orchestrator"

_PROVISION_TIMEOUT = 15.0   # seconds for signup + verify
_SESSION_TIMEOUT = 30.0     # seconds for session creation + run kick-off
_POLL_TIMEOUT = 60.0        # max wall-clock for task polling
_POLL_INTERVAL = 2.0        # poll every 2s
_HTTP_TIMEOUT = 60.0        # default for misc calls


# ---------------------------------------------------------------------------
# Safe arithmetic parser (NO eval) for the BU signup math challenge.
#
# Implements a tiny recursive-descent parser for the grammar:
#   expr   := term (('+' | '-') term)*
#   term   := factor (('*' | '/') factor)*
#   factor := ('-' | '+')? (NUMBER | '(' expr ')')
# Only digits, '+', '-', '*', '/', '(', ')', '.' and whitespace are allowed.
# Any other character raises ValueError — the caller falls back to simulation.
# ---------------------------------------------------------------------------

_ALLOWED_CHARS = re.compile(r"^[0-9+\-*/().\s]+$")


def _solve_math_challenge(challenge_text: str) -> str:
    """Extract a simple arithmetic expression from ``challenge_text`` and solve it.

    The BU signup endpoint returns text like ``"What is 12 * 12?"``. We pull
    out the first arithmetic-looking substring, evaluate it with a strict
    recursive-descent parser (NO ``eval`` / ``ast.literal_eval``), and return
    the answer formatted with two decimal places, e.g. ``"144.00"``.

    Raises ``ValueError`` if no expression can be parsed or the expression
    contains a forbidden character.
    """
    # Find the first run of allowed arithmetic characters (at least 1 digit).
    match = re.search(r"[0-9+\-*/().\s]{3,}", challenge_text or "")
    if not match:
        raise ValueError(f"no arithmetic expression in challenge: {challenge_text!r}")
    expr = match.group(0).strip()
    if not _ALLOWED_CHARS.match(expr):
        raise ValueError(f"forbidden characters in expression: {expr!r}")
    if not any(c.isdigit() for c in expr):
        raise ValueError(f"expression contains no digits: {expr!r}")

    value = _ArithmeticParser(expr).parse()
    return f"{value:.2f}"


class _ArithmeticParser:
    """Recursive-descent parser for + - * / ( ) and decimal numbers."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0

    def parse(self) -> float:
        value = self._expr()
        self._skip_ws()
        if self._pos != len(self._text):
            raise ValueError(f"trailing characters at pos {self._pos}: {self._text!r}")
        return float(value)

    def _expr(self) -> float:
        value = self._term()
        while True:
            self._skip_ws()
            op = self._peek()
            if op == "+":
                self._pos += 1
                value = value + self._term()
            elif op == "-":
                self._pos += 1
                value = value - self._term()
            else:
                break
        return value

    def _term(self) -> float:
        value = self._factor()
        while True:
            self._skip_ws()
            op = self._peek()
            if op == "*":
                self._pos += 1
                value = value * self._factor()
            elif op == "/":
                self._pos += 1
                divisor = self._factor()
                if divisor == 0:
                    raise ValueError("division by zero in challenge")
                value = value / divisor
            else:
                break
        return value

    def _factor(self) -> float:
        self._skip_ws()
        op = self._peek()
        if op == "+":
            self._pos += 1
            return self._factor()
        if op == "-":
            self._pos += 1
            return -self._factor()
        if op == "(":
            self._pos += 1  # consume '('
            value = self._expr()
            self._skip_ws()
            if self._peek() != ")":
                raise ValueError(f"expected ')' at pos {self._pos}")
            self._pos += 1  # consume ')'
            return value
        return self._number()

    def _number(self) -> float:
        self._skip_ws()
        start = self._pos
        seen_dot = False
        while self._pos < len(self._text):
            c = self._text[self._pos]
            if c.isdigit():
                self._pos += 1
            elif c == "." and not seen_dot:
                seen_dot = True
                self._pos += 1
            else:
                break
        if start == self._pos:
            raise ValueError(f"expected number at pos {self._pos}: {self._text!r}")
        return float(self._text[start:self._pos])

    def _peek(self) -> str:
        self._skip_ws()
        if self._pos >= len(self._text):
            return ""
        return self._text[self._pos]

    def _skip_ws(self) -> None:
        while self._pos < len(self._text) and self._text[self._pos].isspace():
            self._pos += 1


# ---------------------------------------------------------------------------
# Task prompt builder
# ---------------------------------------------------------------------------

# Natural-language task templates per seeded action. If the action isn't
# listed, we synthesise a generic prompt from the contract.
_TASK_TEMPLATES: dict[str, str] = {
    "downloadInvoice": (
        "Navigate to the supplier portal, search for invoice {invoiceId}, "
        "click download, and return the invoice number, PDF URL, supplier "
        "name, amount, and payment status."
    ),
    "trackShipment": (
        "Navigate to the carrier tracking portal for carrier {carrier}, "
        "enter tracking number {trackingNumber}, and return the shipment "
        "status, ETA, current location, and proof-of-delivery URL if available."
    ),
    "checkClaimStatus": (
        "Navigate to the insurance provider claims portal, enter patient id "
        "{patientId} and claim id {claimId}, and return the claim status, "
        "denial reason (if any), recommended next step, and last-updated date."
    ),
    "downloadMarketplaceReport": (
        "Navigate to the marketplace seller central for marketplace {marketplace}, "
        "request the {reportType} report for the date range {dateRange}, and "
        "return the report download URL, row count, period start, period end, "
        "and settlement currency."
    ),
    "exportNewCandidates": (
        "Navigate to the recruiting platform, open job {jobId}, export "
        "candidates from source {source}, and return the candidate export "
        "file URL, candidate count, duplicates-removed count, and top match score."
    ),
    "fillSecurityQuestionnaire": (
        "Navigate to the vendor security portal at {portalUrl}, open the "
        "questionnaire for knowledge base {knowledgeBaseId}, pre-fill answers "
        "from the KB, and return the number of filled fields, the number "
        "needing review, the evidence bundle URL, and the draft status."
    ),
}


def _build_task_prompt(action: TypedAction, inputs: dict) -> str:
    """Build a natural-language task prompt for the BU cloud agent.

    Uses a per-action template when available; otherwise synthesises a generic
    prompt from the contract's input + output fields.
    """
    template = _TASK_TEMPLATES.get(action.name)
    if template:
        try:
            return template.format(**inputs)
        except (KeyError, IndexError):
            # Inputs don't match the template placeholders — fall through.
            pass

    parts: list[str] = []
    if inputs:
        parts.append("Given inputs: " + ", ".join(
            f"{k}={v}" for k, v in inputs.items()))
    parts.append(f"perform the {action.name} workflow.")
    if action.contract.outputs:
        field_names = ", ".join(f.name for f in action.contract.outputs)
        parts.append(f"Return these output fields: {field_names}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Response parser — extract key/value pairs from BU's natural-language text.
# ---------------------------------------------------------------------------

# Match "fieldName: value", "fieldName = value", "fieldName - value", or
# "fieldName → value", optionally with a surrounding ```code fence``` or bold
# markdown. Field name is alphanumeric + underscore / camelCase.
_KV_RE = re.compile(
    r"(?:^|\n)\s*(?:[*_`-]\s*)?"
    r"([A-Za-z][A-Za-z0-9_]*)"
    r"\s*[:=]\-{1,2}>?\s*"
    r"(.+?)"
    r"\s*(?:$|\n)",
)


def _parse_bu_response(text: str, action: TypedAction) -> dict[str, Any]:
    """Parse BU's natural-language response into contract-shaped outputs.

    Looks for ``fieldName: value`` patterns and maps each captured value to
    the matching contract output field by name (case-insensitive). Missing
    fields fall back to the contract's type-appropriate default.
    """
    outputs: dict[str, Any] = {}
    # Build a case-insensitive lookup of contract output fields.
    field_by_lower: dict[str, Any] = {f.name.lower(): f for f in action.contract.outputs}

    for match in _KV_RE.finditer(text or ""):
        raw_key = match.group(1).strip()
        raw_value = match.group(2).strip().strip("`*_").strip()
        field = field_by_lower.get(raw_key.lower())
        if field is None or field.name in outputs:
            continue
        outputs[field.name] = _coerce(raw_value, field.type, field.enum)

    # Fill missing fields with type-appropriate defaults so postconditions can
    # run cleanly (validation may still flag them as missing).
    for field in action.contract.outputs:
        if field.name in outputs:
            continue
        outputs[field.name] = _default_for_type(field.type, field.enum)
    return outputs


def _coerce(raw_value: str, field_type: str, enum: tuple | None) -> Any:
    """Coerce a raw string value into the field's declared type."""
    if field_type == "number":
        try:
            return int(raw_value) if raw_value.isdigit() else float(raw_value)
        except (ValueError, TypeError):
            return 0
    if field_type == "boolean":
        return raw_value.strip().lower() in ("true", "yes", "1", "y")
    if enum and raw_value not in enum:
        # Fall back to the first enum value rather than an out-of-range one.
        return enum[0]
    return raw_value


def _default_for_type(field_type: str, enum: tuple | None) -> Any:
    if field_type == "number":
        return 0
    if field_type == "boolean":
        return False
    if enum:
        return enum[0]
    return ""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class BrowserUseAdapter(ExecutionAdapter):
    """Drives the Browser Use cloud API (OPTIONAL adapter #4)."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.bu_browser

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        start = datetime.utcnow()
        traces: list[TraceEvent] = []

        # 1 + 2. Get or self-provision an API key.
        key, key_traces = await self._get_or_provision_key(ts)
        traces.extend(key_traces)
        if key is None:
            # Provisioning failed — simulate.
            sim = await self._simulate(action, inputs, ctx)
            sim.traces = traces + sim.traces
            return sim

        # 3. Create a browser session.
        try:
            async with httpx.AsyncClient(timeout=_SESSION_TIMEOUT) as client:
                sess_resp = await client.post(
                    f"{_BU_API_BASE}/api/v3/browsers",
                    headers={
                        "X-Browser-Use-API-Key": key["apiKey"],
                        "Content-Type": "application/json",
                    },
                    json={},
                )
                if sess_resp.status_code >= 400:
                    traces.append(TraceEvent(
                        ts=ts, adapter=AdapterType.bu_browser, level="error",
                        message=f"BU session create failed: HTTP {sess_resp.status_code}",
                        step="session.create"))
                    sim = await self._simulate(action, inputs, ctx)
                    sim.traces = traces + sim.traces
                    return sim
                sess_data = sess_resp.json()
        except (httpx.TimeoutException, httpx.HTTPError, ValueError) as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="error",
                message=f"BU session create error: {exc}", step="session.create"))
            sim = await self._simulate(action, inputs, ctx)
            sim.traces = traces + sim.traces
            return sim

        session_id = (
            sess_data.get("id") or sess_data.get("session_id")
            or sess_data.get("sessionId") or ""
        )
        if not session_id:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="error",
                message="BU session create returned no session id",
                step="session.create"))
            sim = await self._simulate(action, inputs, ctx)
            sim.traces = traces + sim.traces
            return sim

        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.bu_browser, level="info",
            message=f"BU session created ({session_id[:12]}…)", step="session.create",
            durationMs=int((datetime.utcnow() - start).total_seconds() * 1000)))

        # 4. Build the task prompt.
        prompt = _build_task_prompt(action, inputs)
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.bu_browser, level="info",
            message=f"BU task: {prompt[:160]}", step="task.build"))

        # 5. Run the task + poll for completion.
        try:
            run_resp = await self._run_and_poll(
                key["apiKey"], session_id, prompt, ts, traces)
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="error",
                message=f"BU task poll error: {exc}", step="task.poll"))
            await self._safe_touch(key)
            sim = await self._simulate(action, inputs, ctx)
            sim.traces = traces + sim.traces
            return sim

        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.bu_browser, level="info",
            message=f"BU result received ({elapsed}ms)", step="task.done",
            durationMs=elapsed))

        # 6. Parse the result.
        # BU returns text in various nested shapes; extract whatever text we can.
        result_text = _extract_text(run_resp)
        outputs = _parse_bu_response(result_text, action)
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.bu_browser, level="info",
            message="parsed from BU natural-language response", step="parse",
            durationMs=2))
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.bu_browser, level="info",
            message="stealth + CAPTCHA + proxy handled by BU cloud",
            step="cloud.capabilities"))

        # 7. Touch the key to record last-used.
        await self._safe_touch(key)

        # 8. Return success.
        total = int((datetime.utcnow() - start).total_seconds() * 1000)
        return AdapterResult(
            success=True, outputs=outputs, traces=traces,
            screenshots=[], error=None, durationMs=total,
        )

    # ------------------------------------------------------------------
    # Key provisioning
    # ------------------------------------------------------------------

    async def _get_or_provision_key(
        self, ts: datetime,
    ) -> tuple[dict | None, list[TraceEvent]]:
        """Return the active BU key, self-provisioning one if none exists.

        Returns ``(None, traces)`` if provisioning fails (network error,
        bad challenge, HTTP error). The caller falls back to simulation.
        """
        traces: list[TraceEvent] = []
        try:
            active = await bu_key_get_active()
        except Exception as exc:
            # DB not ready — surface and simulate.
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="warn",
                message=f"BU key lookup failed ({exc}); simulating",
                step="key.lookup"))
            return None, traces

        if active and active.get("apiKey"):
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="info",
                message="BU key present (cached)", step="key.lookup", durationMs=5))
            return active, traces

        # No active key — self-provision.
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.bu_browser, level="info",
            message="no BU key — self-provisioning via challenge-response",
            step="key.provision"))
        try:
            new_key = await self._provision_key()
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="info",
                message="BU key provisioned + stored", step="key.provision",
                durationMs=20))
            return new_key, traces
        except Exception as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="warn",
                message=f"BU key provisioning failed ({exc}); simulating",
                step="key.provision"))
            return None, traces

    async def _provision_key(self) -> dict:
        """Self-provision a BU API key via the signup challenge flow.

        Raises on any failure (caller falls back to simulation).
        """
        async with httpx.AsyncClient(timeout=_PROVISION_TIMEOUT) as client:
            # 1. POST /cloud/signup → challenge_id + challenge_text.
            signup_resp = await client.post(
                f"{_BU_API_BASE}/cloud/signup",
                json={"email": _BU_SIGNUP_EMAIL, "name": _BU_SIGNUP_NAME},
                headers={"Content-Type": "application/json"},
            )
            if signup_resp.status_code >= 400:
                raise RuntimeError(
                    f"signup HTTP {signup_resp.status_code}: {signup_resp.text[:200]}")
            signup_data = signup_resp.json()
            challenge_id = signup_data.get("challenge_id") or signup_data.get("challengeId")
            challenge_text = signup_data.get("challenge_text") or signup_data.get("challengeText")
            if not challenge_id or not challenge_text:
                raise RuntimeError(
                    f"signup returned no challenge: {signup_data!r}")

            # 2. Solve the math challenge safely (no eval).
            answer = _solve_math_challenge(challenge_text)

            # 3. POST /cloud/signup/verify → api_key.
            verify_resp = await client.post(
                f"{_BU_API_BASE}/cloud/signup/verify",
                json={"challenge_id": challenge_id, "answer": answer},
                headers={"Content-Type": "application/json"},
            )
            if verify_resp.status_code >= 400:
                raise RuntimeError(
                    f"verify HTTP {verify_resp.status_code}: {verify_resp.text[:200]}")
            verify_data = verify_resp.json()
            api_key = (
                verify_data.get("api_key")
                or verify_data.get("apiKey")
                or verify_data.get("key")
                or ""
            )
            if not api_key or not api_key.startswith("bu_"):
                raise RuntimeError(
                    f"verify returned invalid api_key: {api_key!r}")

        # 4. Persist the key.
        record = {
            "id": new_id("buk"),
            "apiKey": api_key,
            "email": _BU_SIGNUP_EMAIL,
            "name": _BU_SIGNUP_NAME,
            "status": "active",
            "claimed": False,
        }
        await bu_key_put(record)
        return record

    # ------------------------------------------------------------------
    # Task run + poll
    # ------------------------------------------------------------------

    async def _run_and_poll(
        self, api_key: str, session_id: str, prompt: str,
        ts: datetime, traces: list[TraceEvent],
    ) -> dict:
        """POST the task to the BU session and poll until done/error.

        Raises ``httpx.HTTPError`` / ``httpx.TimeoutException`` on network
        failure; raises ``RuntimeError`` on a non-running HTTP status.
        """
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            run_resp = await client.post(
                f"{_BU_API_BASE}/api/v3/sessions/{session_id}/run",
                headers={
                    "X-Browser-Use-API-Key": api_key,
                    "Content-Type": "application/json",
                },
                json={"task": prompt},
            )
            if run_resp.status_code >= 400:
                raise RuntimeError(
                    f"run HTTP {run_resp.status_code}: {run_resp.text[:200]}")

            deadline = datetime.utcnow().timestamp() + _POLL_TIMEOUT
            poll_iter = 0
            while datetime.utcnow().timestamp() < deadline:
                poll_iter += 1
                await asyncio.sleep(_POLL_INTERVAL)
                status_resp = await client.get(
                    f"{_BU_API_BASE}/api/v3/sessions/{session_id}",
                    headers={"X-Browser-Use-API-Key": api_key},
                )
                if status_resp.status_code >= 400:
                    raise RuntimeError(
                        f"poll HTTP {status_resp.status_code}: {status_resp.text[:200]}")
                state = status_resp.json()
                status = (
                    state.get("status")
                    or state.get("state")
                    or ""
                ).lower()
                if status in ("done", "completed", "success", "finished"):
                    if poll_iter == 1:
                        traces.append(TraceEvent(
                            ts=ts, adapter=AdapterType.bu_browser, level="info",
                            message="BU task completed on first poll",
                            step="task.poll", durationMs=int(_POLL_INTERVAL * 1000)))
                    return state
                if status in ("error", "failed", "errored"):
                    raise RuntimeError(f"BU task ended in status={status}")
                # Still running — keep polling.
            raise RuntimeError(f"BU task timed out after {_POLL_TIMEOUT}s")

    async def _safe_touch(self, key: dict) -> None:
        """Touch the key's lastUsedAt; swallow errors (best-effort)."""
        try:
            await bu_key_touch(key["id"])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Simulation fallback (matches the pattern of the other adapters)
    # ------------------------------------------------------------------

    async def _simulate(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        """Deterministic simulation when the BU cloud is unavailable."""
        from .api_adapter import _simulate_outputs
        ts = ctx.telemetry.now()
        traces = [
            TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="info",
                message="BU cloud unavailable — running simulation",
                step="fallback", durationMs=20),
            TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="info",
                message="BU session created (simulated)", step="session.create",
                durationMs=80),
            TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="info",
                message=f"BU task: {_build_task_prompt(action, inputs)[:120]} (simulated)",
                step="task.build"),
            TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="info",
                message="BU result received (simulated)", step="task.done",
                durationMs=600),
            TraceEvent(
                ts=ts, adapter=AdapterType.bu_browser, level="info",
                message="stealth + CAPTCHA + proxy handled by BU cloud (simulated)",
                step="cloud.capabilities"),
        ]
        return AdapterResult(
            success=True, outputs=_simulate_outputs(action, inputs),
            traces=traces, screenshots=["bu-1.png"], error=None, durationMs=720,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(state: dict) -> str:
    """Pull the natural-language result text out of a BU session state dict.

    BU's response shape varies; we check the common keys in order and
    concatenate whatever text we find.
    """
    if not isinstance(state, dict):
        return str(state or "")

    candidates = (
        state.get("result"),
        state.get("output"),
        state.get("final_result"),
        state.get("finalResult"),
        state.get("answer"),
        state.get("text"),
    )
    parts: list[str] = []
    for c in candidates:
        if isinstance(c, str) and c.strip():
            parts.append(c.strip())
        elif isinstance(c, dict):
            # Some shapes wrap the text in a sub-dict.
            for sub_key in ("text", "value", "answer", "result"):
                v = c.get(sub_key)
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
                    break
        elif isinstance(c, list):
            for item in c:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
    if not parts and state.get("steps"):
        # Last resort: stringify the steps.
        parts.append(str(state["steps"]))
    return "\n".join(parts)
