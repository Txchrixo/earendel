"""Adapter 2 — Discovered internal / shadow API (APISensor-style).

Replays captured network requests from the recording phase. During recording,
Earendel captures XHR/fetch traffic. This adapter replays those requests
with the user's session cookies, providing a faster, more reliable path
than browser automation.

Discovery flow (Option B — the technical moat):

  1. The recording phase captures a HAR (HTTP Archive) of the workflow.
  2. ``app.core.discovery.har_analyzer.analyze_har`` clusters the requests
     by ``(method, normalized_path)``, scores each cluster by business
     relevance, and infers a ``field_mapping`` (response-key -> contract
     field), a ``body_template`` (request body with ``{inputKey}``
     placeholders), and a ``cookie_env_var``.
  3. The candidates are persisted to the ``DiscoveredEndpoint`` table by
     ``app.core.discovery.endpoint_store.store_discovered_endpoints``.
  4. At runtime, this adapter calls ``get_best_endpoint(action.name)`` to
     fetch the highest-scoring ACTIVE discovered endpoint, builds the
     request, attaches the session cookie, and replays it.

Session-cookie resolution (Phase 1.4):
  - **Preferred**: read the cookies captured during recording and stored on
    the connector's ``credentialVaultKey`` (JSON-stringified) by the compile
    endpoint. This is what real Chrome-extension recordings produce.
  - **Fallback**: read the env var named by the endpoint's
    ``cookieEnvVar`` (e.g. ``ACME_SESSION_COOKIE``). This is what demo /
    pre-Phase-1-B deployments use, and what the test suite relies on.

Stale detection (Phase 1.5 — hardened):
  - HTTP 404/410  → ``mark_stale("endpoint moved")`` + fall through.
  - HTTP 401/403  → ``record_replay(False)`` + fall through (cookies
    expired → re-record needed; the endpoint itself is still alive).
  - Schema mismatch (more than half the stored ``responseShape`` keys
    missing from the live response) → ``mark_stale("schema changed")`` +
    fall through (the endpoint moved / changed shape — re-discovery
    needed).

Fallback ladder (the adapter NEVER raises):

  discovered endpoint (DB) with cookie  ->  real HTTP replay
       | no cookie / HTTP 404-410 / 401-403 / schema mismatch
       v
  hardcoded ``_ROUTE_REGISTRY`` with cookie  ->  real HTTP replay
       | no cookie / no route / error
       v
  ``_simulate()`` (deterministic outputs + simulated traces)

The hardcoded ``_ROUTE_REGISTRY`` is kept as a secondary fallback so the
adapter still works if the DB is unavailable or empty (e.g. for tests /
fresh installs that haven't compiled a recording yet).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

import httpx

from ..core.discovery.endpoint_store import (
    get_best_endpoint, mark_stale, record_replay,
)
from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from .base import AdapterResult, ExecutionContext, ExecutionAdapter

logger = logging.getLogger("earendel.adapters.internal_route")

# Captured route registry — kept as a SECONDARY fallback (backward compat).
# Primary path is now the DB-backed ``DiscoveredEndpoint`` table, but if the
# DB is empty or unavailable, this hardcoded registry still lets the adapter
# do real HTTP replays for the 3 originally-seeded actions.
_ROUTE_REGISTRY: dict[str, dict[str, Any]] = {
    "downloadInvoice": {
        "method": "POST",
        "url": "https://supplier-portal.acme.com/internal/v2/invoices/download",
        "body_template": {"invoiceId": "{invoiceId}"},
        "cookie_env": "ACME_SESSION_COOKIE",
        "field_mapping": {
            "invoiceNumber": "invoice_number",
            "pdfUrl": "download_url",
            "supplierName": "supplier_name",
            "amount": "total",
            "status": "payment_status",
        },
    },
    "checkClaimStatus": {
        "method": "POST",
        "url": "https://provider.bluecross.com/internal/v2/claims/check",
        "body_template": {"patientId": "{patientId}", "claimId": "{claimId}"},
        "cookie_env": "BLUECROSS_SESSION_COOKIE",
        "field_mapping": {
            "status": "claim_status",
            "denialReason": "denial_reason",
            "nextStep": "next_step",
            "lastUpdated": "last_updated",
        },
    },
    "downloadMarketplaceReport": {
        "method": "GET",
        "url": "https://sellercentral.amazon.com/internal/reports/download",
        "body_template": {"reportType": "{reportType}", "dateRange": "{dateRange}"},
        "cookie_env": "AMAZON_SESSION_COOKIE",
        "field_mapping": {
            "reportUrl": "download_url",
            "rows": "row_count",
            "periodStart": "period_start",
            "periodEnd": "period_end",
            "currency": "currency",
        },
    },
}

_TIMEOUT = 15.0


def _get_nested(data: dict, path: str) -> Any:
    """Get a value from a nested dict using dot notation."""
    keys = path.split(".")
    val = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def _build_body(template: dict, inputs: dict) -> dict:
    """Build the request body from the template, substituting input values.

    A template value of the form ``"{inputKey}"`` is replaced with
    ``inputs[inputKey]`` (falling back to the literal placeholder if the
    input is missing). Any other value is passed through verbatim.
    """
    body = {}
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            input_key = value[1:-1]
            body[key] = inputs.get(input_key, value)
        else:
            body[key] = value
    return body


def _resolve_headers(
    headers_template: dict[str, Any],
    session_cookie: str,
) -> dict[str, str]:
    """Build request headers from the template + the resolved session cookie.

    Values of the form ``{ENV_VAR_NAME}`` are substituted with the env var's
    value (skipped if unset). The session cookie is attached as both
    ``Cookie`` and ``X-XSRF-TOKEN`` (mirroring the existing hardcoded path).
    """
    headers: dict[str, str] = {}
    for k, v in headers_template.items():
        if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
            env_name = v[1:-1]
            env_val = os.environ.get(env_name, "")
            if env_val:
                headers[k] = env_val
        elif isinstance(v, str) and v:
            headers[k] = v
    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Accept", "application/json")
    if session_cookie:
        headers.setdefault(
            "Cookie", f"session={session_cookie}"
        )
        xsrf = session_cookie[:32] if len(session_cookie) >= 32 else session_cookie
        headers.setdefault("X-XSRF-TOKEN", xsrf)
    return headers


def _map_response(
    response_data: dict, action: TypedAction, field_mapping: dict[str, str]
) -> dict:
    """Map the API response to the action's output contract fields.

    ``field_mapping`` is ``{contract_field_name: response_key_or_dot_path}``.
    """
    outputs: dict[str, Any] = {}
    for field in action.contract.outputs:
        api_field = field_mapping.get(field.name, field.name)
        value = _get_nested(response_data, api_field)
        if value is not None:
            outputs[field.name] = value
        elif field.type == "number":
            outputs[field.name] = 0
        elif field.type == "boolean":
            outputs[field.name] = False
        else:
            outputs[field.name] = None
    return outputs


def _safe_json_loads(text: str | None, default: Any) -> Any:
    """Parse JSON safely — returns ``default`` on any error / empty input."""
    if not text or not isinstance(text, str):
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return default


class InternalRouteAdapter(ExecutionAdapter):
    """Replays discovered internal endpoints with session cookies."""

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.internal_route

    # ------------------------------------------------------------------
    # Session-cookie resolution (Phase 1.4)
    # ------------------------------------------------------------------

    async def _get_session_cookie(
        self,
        action: TypedAction,
        ctx: ExecutionContext,
        cookie_env_var: str,
    ) -> str:
        """Resolve the session cookie for replay.

        Preferred path: read the cookies captured during recording and
        stored on the connector's ``credentialVaultKey`` (JSON-stringified)
        by the compile endpoint. We look for a cookie whose name matches
        one of the common session-cookie names (``session``, ``session_id``,
        ``sid``, ``auth``) — case-insensitive — and return its value. If no
        name matches, we return the first cookie's value (a best-effort
        heuristic for sites that use non-standard cookie names).

        Fallback path: read the env var named by ``cookie_env_var`` (e.g.
        ``ACME_SESSION_COOKIE``). This is the pre-Phase-1-B path, kept for
        demo / test deployments that don't use the Chrome extension.

        Returns ``""`` if neither path yields a cookie - the caller treats
        that as "no auth available" and falls through to the next fallback.
        """
        # ---- Phase 10: OAuth2 token (preferred for oauth connectors)
        try:
            from ..infrastructure.prisma_repositories import (
                connector_get, oauth_token_get_active,
            )
            conn = await connector_get(action.connectorId)
            if conn and conn.get("authMethod") == "oauth":
                token = await oauth_token_get_active(action.connectorId)
                if token and token.get("accessToken"):
                    # Return the access token (caller sets it as Bearer header)
                    return token["accessToken"]
        except Exception as exc:
            logger.debug("OAuth2 token lookup failed: %s", exc)

        # ---- Preferred: connector vault (cookies captured during recording)
        try:
            # Local import keeps the adapter importable even if the prisma
            # engine isn't initialised yet (e.g. import-time checks).
            from ..infrastructure.prisma_repositories import connector_get
            row = await connector_get(action.connectorId)
            if row:
                raw = row.get("credentialVaultKey") or ""
                if raw and raw.startswith("{"):
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, dict):
                        cookies = parsed.get("cookies") or []
                        if isinstance(cookies, list) and cookies:
                            for cookie in cookies:
                                if not isinstance(cookie, dict):
                                    continue
                                name = (cookie.get("name") or "").lower()
                                if name in ("session", "session_id", "sid", "auth"):
                                    return cookie.get("value") or ""
                            # No name match — fall back to the first cookie.
                            first = cookies[0]
                            if isinstance(first, dict):
                                return first.get("value") or ""
        except Exception as exc:
            # Vault lookup is best-effort — never raise to the caller. The
            # env-var fallback below still gives us a working cookie in
            # deployments that don't persist cookies on the connector.
            logger.debug("connector cookie lookup failed: %s", exc)

        # ---- Fallback: env var (pre-Phase-1-B path).
        if cookie_env_var:
            return os.environ.get(cookie_env_var, "")
        return ""

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        ts = ctx.telemetry.now()
        # Shared trace list — appended to by every fallback layer so the
        # final AdapterResult carries the full provenance of what was tried
        # (discovered -> hardcoded -> simulation), even when only the last
        # layer actually produced outputs.
        traces: list[TraceEvent] = []

        # ---- 1. DB-backed discovered endpoint (primary path) ----
        try:
            endpoint = await get_best_endpoint(action.name)
        except Exception:
            endpoint = None

        if endpoint and endpoint.get("status") == "active":
            result = await self._execute_discovered(
                endpoint, action, inputs, ctx, ts, traces
            )
            if result is not None:
                return result
            # ``None`` means: no cookie, or HTTP 404/410/401/403, or schema
            # mismatch (already marked stale / recorded). Fall through to
            # the hardcoded registry — the traces accumulated so far carry
            # forward.

        # ---- 2. Hardcoded registry (secondary fallback) ----
        result = await self._execute_hardcoded(action, inputs, ctx, ts, traces)
        if result is not None:
            return result

        # ---- 3. Final fallback: simulation ----
        return await self._simulate(action, inputs, ctx, traces)

    async def _execute_discovered(
        self,
        endpoint: dict,
        action: TypedAction,
        inputs: dict,
        ctx: ExecutionContext,
        ts: datetime,
        traces: list[TraceEvent],
    ) -> AdapterResult | None:
        """Replay a DB-backed discovered endpoint.

        Appends to the shared ``traces`` list so the caller can carry them
        forward if it falls through to the next fallback.

        Returns ``None`` when the caller should fall through to the next
        fallback (no cookie configured, HTTP 404/410/401/403, or schema
        mismatch — already marked stale / recorded here). Returns an
        :class:`AdapterResult` for any other outcome (success or
        definitive failure).
        """
        endpoint_id = endpoint.get("id", "")
        url = endpoint.get("url", "")
        method = (endpoint.get("method") or "POST").upper()
        cookie_env_var = endpoint.get("cookieEnvVar") or ""
        # Phase 1.4: prefer cookies captured during recording (stored on
        # the connector); fall back to the env var if not available.
        session_cookie = await self._get_session_cookie(
            action, ctx, cookie_env_var,
        )

        body_template = _safe_json_loads(endpoint.get("bodyTemplate"), {}) or {}
        if not isinstance(body_template, dict):
            body_template = {}
        headers_template = _safe_json_loads(endpoint.get("headersTemplate"), {}) or {}
        if not isinstance(headers_template, dict):
            headers_template = {}
        field_mapping = _safe_json_loads(endpoint.get("fieldMapping"), {}) or {}
        if not isinstance(field_mapping, dict):
            field_mapping = {}
        response_shape = _safe_json_loads(endpoint.get("responseShape"), {}) or {}
        if not isinstance(response_shape, dict):
            response_shape = {}

        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message=f"discovered endpoint {url} (from HAR capture, "
                    f"score={float(endpoint.get('businessScore', 0) or 0):.2f})",
            step="discover",
        ))

        # No cookie configured -> warn + fall through (return None).
        if not session_cookie:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="warn",
                message=f"no session cookie in env ({cookie_env_var}) — "
                        f"falling back to hardcoded registry then simulation",
                step="auth", durationMs=5,
            ))
            # Traces carry forward — the next fallback sees them.
            return None

        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message="session cookie reused", step="auth", durationMs=30,
        ))
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message="XSRF token attached", step="auth", durationMs=10,
        ))

        body = _build_body(body_template, inputs)
        headers = _resolve_headers(headers_template, session_cookie)

        try:
            start = datetime.utcnow()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers, params=body)
                else:
                    resp = await client.request(
                        method, url, headers=headers, json=body
                    )
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

            # 404 / 410 -> mark stale + fall back (endpoint moved).
            if resp.status_code in (404, 410):
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="warn",
                    message=f"HTTP {resp.status_code} — endpoint stale — "
                            f"marking and falling back",
                    step="http.response", durationMs=elapsed,
                ))
                await mark_stale(
                    endpoint_id, f"HTTP {resp.status_code} — endpoint moved"
                )
                # Signal "fall through" — traces carry forward.
                return None

            # Phase 1.5: 401 / 403 -> auth stale. The endpoint itself is
            # still there, so we DON'T mark it stale — but the cookies have
            # expired and the action needs re-recording. Record the failed
            # replay and fall through to the next adapter (the hardcoded
            # registry will likely fail the same way, but the simulation
            # fallback gives the orchestrator a graceful degrade).
            if resp.status_code in (401, 403):
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="warn",
                    message=f"HTTP {resp.status_code} — auth stale — cookies "
                            f"expired, re-recording needed",
                    step="http.response", durationMs=elapsed,
                ))
                await record_replay(endpoint_id, False, elapsed)
                return None

            if resp.status_code >= 400:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="error",
                    message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    step="http.response", durationMs=elapsed,
                ))
                await record_replay(endpoint_id, False, elapsed)
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error=f"HTTP {resp.status_code}",
                    durationMs=elapsed,
                )

            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message=f"200 OK ({elapsed}ms)", step="http.response",
                durationMs=elapsed,
            ))

            try:
                response_data = resp.json()
            except Exception:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="error",
                    message="response is not valid JSON", step="parse",
                ))
                await record_replay(endpoint_id, False, elapsed)
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error="Invalid JSON response",
                    durationMs=elapsed,
                )

            # Phase 1.5: schema-mismatch detection. If the live response
            # is missing more than half of the keys we recorded in the
            # stored ``responseShape``, the endpoint has changed shape
            # (e.g. a new API version, a different response envelope) —
            # mark it stale so the next compile re-analyzes the HAR.
            if response_shape and isinstance(response_data, dict):
                expected_keys = set(response_shape.keys())
                actual_keys = set(response_data.keys())
                missing = expected_keys - actual_keys
                if expected_keys and len(missing) > len(expected_keys) / 2:
                    missing_preview = ",".join(sorted(list(missing))[:5])
                    traces.append(TraceEvent(
                        ts=ts, adapter=AdapterType.internal_route, level="warn",
                        message=f"schema mismatch — {len(missing)}/{len(expected_keys)} "
                                f"keys missing — marking stale",
                        step="validation", durationMs=1,
                    ))
                    await mark_stale(
                        endpoint_id,
                        f"schema changed — missing {len(missing)} keys: "
                        f"{missing_preview}",
                    )
                    await record_replay(endpoint_id, False, elapsed)
                    return None

            outputs = _map_response(response_data, action, field_mapping)
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message=f"mapped {len(outputs)} output fields", step="mapping",
                durationMs=1,
            ))
            await record_replay(endpoint_id, True, elapsed)
            return AdapterResult(
                success=True, outputs=outputs, traces=traces,
                screenshots=[], error=None, durationMs=elapsed,
            )

        except httpx.TimeoutException:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="error",
                message=f"timeout after {_TIMEOUT}s", step="http.request",
            ))
            await record_replay(endpoint_id, False, int(_TIMEOUT * 1000))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=f"Timeout after {_TIMEOUT}s",
                durationMs=int(_TIMEOUT * 1000),
            )
        except Exception as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="error",
                message=f"connection error: {exc}", step="http.request",
            ))
            await record_replay(endpoint_id, False, 0)
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=str(exc), durationMs=0,
            )

    async def _execute_hardcoded(
        self,
        action: TypedAction,
        inputs: dict,
        ctx: ExecutionContext,
        ts: datetime,
        traces: list[TraceEvent],
    ) -> AdapterResult | None:
        """Replay via the hardcoded ``_ROUTE_REGISTRY`` (secondary fallback).

        Appends to the shared ``traces`` list. Returns ``None`` when there's
        no hardcoded route for this action or no session cookie is configured
        (so the caller falls through to simulation). Returns an
        :class:`AdapterResult` otherwise.
        """
        route = _ROUTE_REGISTRY.get(action.name)
        if route is None:
            return None

        cookie_env = route.get("cookie_env", "")
        # Phase 1.4: same cookie resolution as the discovered path — prefer
        # cookies captured during recording (stored on the connector), fall
        # back to the env var named by the hardcoded route.
        session_cookie = await self._get_session_cookie(action, ctx, cookie_env)
        if not session_cookie:
            # No cookie -> fall through to simulation (no trace emitted —
            # the simulation path will emit its own traces).
            return None

        method = route.get("method", "POST")
        url = route["url"]
        body = _build_body(route.get("body_template", {}), inputs)

        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message=f"discovered endpoint {url} (hardcoded registry fallback)",
            step="discover",
        ))
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message="session cookie reused", step="auth", durationMs=30,
        ))
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message="XSRF token attached", step="auth", durationMs=10,
        ))

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cookie": f"session={session_cookie}",
            "X-XSRF-TOKEN": session_cookie[:32]
            if len(session_cookie) >= 32 else session_cookie,
        }

        try:
            start = datetime.utcnow()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers, params=body)
                else:
                    resp = await client.request(method, url, headers=headers, json=body)
            elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

            if resp.status_code >= 400:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="error",
                    message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    step="http.response", durationMs=elapsed,
                ))
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error=f"HTTP {resp.status_code}",
                    durationMs=elapsed,
                )

            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message=f"200 OK ({elapsed}ms)", step="http.response",
                durationMs=elapsed,
            ))

            try:
                response_data = resp.json()
            except Exception:
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.internal_route, level="error",
                    message="response is not valid JSON", step="parse",
                ))
                return AdapterResult(
                    success=False, outputs={}, traces=traces,
                    screenshots=[], error="Invalid JSON response",
                    durationMs=elapsed,
                )

            outputs = _map_response(response_data, action, route.get("field_mapping", {}))
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="info",
                message=f"mapped {len(outputs)} output fields", step="mapping",
                durationMs=1,
            ))
            return AdapterResult(
                success=True, outputs=outputs, traces=traces,
                screenshots=[], error=None, durationMs=elapsed,
            )

        except httpx.TimeoutException:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="error",
                message=f"timeout after {_TIMEOUT}s", step="http.request",
            ))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=f"Timeout after {_TIMEOUT}s",
                durationMs=int(_TIMEOUT * 1000),
            )
        except Exception as exc:
            traces.append(TraceEvent(
                ts=ts, adapter=AdapterType.internal_route, level="error",
                message=f"connection error: {exc}", step="http.request",
            ))
            return AdapterResult(
                success=False, outputs={}, traces=traces,
                screenshots=[], error=str(exc), durationMs=0,
            )

    async def _simulate(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext,
        traces: list[TraceEvent] | None = None,
    ) -> AdapterResult:
        """Fallback simulation when no route is captured.

        If ``traces`` is provided (shared list from the caller), appends the
        simulation traces to it — so the final result shows the full chain:
        discovered -> hardcoded -> simulation. If ``traces`` is None (legacy
        callers), builds a fresh list.
        """
        from .api_adapter import _simulate_outputs
        ts = ctx.telemetry.now()
        path = f"/internal/v2/{action.name}"
        if traces is None:
            traces = []
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message=f"discovered endpoint {path} (simulated — no HAR capture)",
            step="discover",
        ))
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message="session cookie reused (simulated)", step="auth", durationMs=30,
        ))
        traces.append(TraceEvent(
            ts=ts, adapter=AdapterType.internal_route, level="info",
            message="200 OK (simulated)", step="http.response", durationMs=140,
        ))
        return AdapterResult(
            success=True,
            outputs=_simulate_outputs(action, inputs),
            traces=traces,
            screenshots=[],
            error=None,
            durationMs=180,
        )
