"""Recordings — FastAPI router."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...api.deps import get_action_registry, get_llm_client
from ...core.discovery.demo_har import _synthesize_demo_har
from ...core.discovery.endpoint_store import store_discovered_endpoints
from ...core.discovery.har_analyzer import analyze_har
from ...infrastructure.llm_client import LLMClient
from . import service

router = APIRouter(prefix="/recordings", tags=["recordings"])

logger = logging.getLogger("earendel.discovery")


class CreateRecordingBody(BaseModel):
    """POST body for creating a recording (real or simulated).

    Real recordings (from the Chrome extension) carry the full capture
    payload: ``steps`` + ``har`` + ``cookies`` + aggregate counters.
    Simulated recordings (frontend "New recording" button) carry only
    ``{connectorId, workflowName}`` — the simulator generates the rest.
    The presence of ``steps`` is the discriminator.
    """

    connectorId: str
    workflowName: str
    # Real-recording fields (Chrome extension, Phase-1-A). All optional so
    # the legacy simulated path keeps working unchanged.
    steps: list[dict[str, Any]] | None = None
    totalDurationMs: int | None = None
    networkRequests: int | None = None
    domMutations: int | None = None
    screenshots: int | None = None
    harCaptured: bool | None = None
    har: dict[str, Any] | None = None
    cookies: list[dict[str, Any]] | None = None


@router.get("")
async def list_recordings_endpoint() -> list[dict[str, Any]]:
    """List all recordings."""
    items = await service.fetch_all()
    return [r.model_dump(mode="json") for r in items]


@router.get("/{recording_id}")
async def get_recording_endpoint(recording_id: str) -> dict[str, Any]:
    """Fetch a single recording."""
    rec = await service.fetch(recording_id)
    return rec.model_dump(mode="json")


@router.post("")
async def create_recording_endpoint(body: CreateRecordingBody) -> dict[str, Any]:
    """Create a recording.

    Two paths:
      1. **Real** — when ``body.steps`` is present, the payload came from the
         Chrome extension (Phase-1-A) and we persist the full capture
         (steps + HAR + cookies + counters) via :func:`service.create_real`.
      2. **Simulated** — when ``body.steps`` is absent, the frontend's "New
         recording" button was clicked; fall back to the deterministic
         simulator so the studio demo keeps working without a live browser.
    """
    if body.steps is not None:
        rec = await service.create_real(
            connector_id=body.connectorId,
            workflow_name=body.workflowName,
            steps=body.steps,
            total_duration_ms=body.totalDurationMs or 0,
            network_requests=body.networkRequests or 0,
            dom_mutations=body.domMutations or 0,
            screenshots=body.screenshots or 0,
            har_captured=body.harCaptured if body.harCaptured is not None else True,
            har=body.har or {},
            cookies=body.cookies or [],
        )
    else:
        rec = await service.create_simulated(body.connectorId, body.workflowName)
    return rec.model_dump(mode="json")


@router.post("/{recording_id}/compile")
async def compile_recording_endpoint(
    recording_id: str,
    registry=Depends(get_action_registry),
    llm: LLMClient = Depends(get_llm_client),
) -> dict[str, Any]:
    """Compile a recording into a TypedAction via the LLM and register it.

    After the LLM compile, this also runs the HAR-based network-discovery
    pipeline: the recording's HAR (real or synthesized) is analyzed into
    scored ``DiscoveredEndpointCandidate`` rows and persisted to the
    ``DiscoveredEndpoint`` table so the ``internal_route`` adapter can
    replay them at runtime.

    Phase-1-B additions:
      - Prefer the real captured HAR (``rec.har.log.entries``) when present.
        Fall back to ``_synthesize_demo_har`` only for simulated recordings
        with no real HAR.
      - After HAR analysis, persist the recording's captured cookies onto
        the connector's ``credentialVaultKey`` so the ``internal_route``
        adapter can replay with the real session at runtime (instead of
        requiring an env var).
    """
    action = await service.compile(recording_id, registry, llm)

    # ---- Network discovery (Option B) -----------------------------------
    rec = await service.fetch(recording_id)

    # Use the real captured HAR if present; fall back to synthesized demo
    # HAR only when the recording has no HAR data (simulated recordings).
    real_har = rec.har if isinstance(rec.har, dict) and rec.har.get("log") else None
    har = None
    if real_har and real_har.get("log", {}).get("entries"):
        har = real_har
        logger.info(
            "using real captured HAR (%d entries) for action %s",
            len(real_har["log"]["entries"]), action.name,
        )
    elif rec.harCaptured:
        har = _synthesize_demo_har(action.name)
        logger.info(
            "no real HAR — using synthesized demo HAR for action %s", action.name,
        )

    discovered_count = 0
    if har is not None:
        try:
            candidates = analyze_har(har, action.name, rec.connectorId)
            discovered_count = await store_discovered_endpoints(
                candidates, action.name, rec.connectorId
            )
            logger.info(
                "discovered %d endpoints from HAR for action %s",
                discovered_count, action.name,
            )
        except Exception as exc:
            # Discovery is best-effort — never fail the compile because the
            # HAR analyzer / store blew up. The internal_route adapter falls
            # back to its hardcoded registry + simulation.
            logger.warning(
                "HAR discovery failed for action %s: %s", action.name, exc,
            )
            discovered_count = 0

    # ---- Persist captured cookies on the connector (Phase 1.4) ----------
    # The internal_route adapter can't see the Recording — it only has the
    # TypedAction + ExecutionContext. So we stash the cookies on the
    # connector's credentialVaultKey (JSON-stringified) during compile, and
    # the adapter reads them back at replay time. In production this would
    # be encrypted by the real vault; for the demo / dev path a plain JSON
    # string in the credentialVaultKey column is sufficient.
    await _persist_cookies_on_connector(rec)

    return {
        "action": action.model_dump(mode="json"),
        "discoveredEndpoints": discovered_count,
    }


async def _persist_cookies_on_connector(recording: Any) -> None:
    """Best-effort: store the recording's captured cookies on its connector.

    MUST NOT raise — cookie persistence is best-effort. If the connector
    can't be fetched / updated (DB unavailable, connector deleted
    mid-compile, malformed cookies, etc.), log a warning and move on; the
    internal_route adapter's env-var fallback still works.
    """
    try:
        cookies_field = recording.cookies
        if not isinstance(cookies_field, dict):
            return
        cookies_list = cookies_field.get("cookies")
        if not cookies_list:
            return
        # Local import avoids a module-load cycle at router-import time and
        # keeps the failure mode (DB not initialised) local to this helper.
        from ..connectors.repository import get_connector, put_connector
        connector = await get_connector(recording.connectorId)
        if connector is None:
            logger.warning(
                "cannot persist cookies — connector %s not found",
                recording.connectorId,
            )
            return
        # Overwrite credentialVaultKey with the JSON-stringified cookies
        # envelope. (In production: encrypt via the real vault.)
        connector.credentialVaultKey = json.dumps(cookies_field)
        await put_connector(connector)
        logger.info(
            "stored %d cookies on connector %s for replay",
            len(cookies_list), recording.connectorId,
        )
    except Exception as exc:
        logger.warning("failed to store cookies on connector: %s", exc)
