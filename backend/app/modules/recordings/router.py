"""Recordings — FastAPI router."""
from __future__ import annotations

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
    """POST body for creating a simulated recording."""
    connectorId: str
    workflowName: str


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
    """Create a simulated recording."""
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
    pipeline: the recording's HAR (or a synthesized demo HAR for the action)
    is analyzed into scored ``DiscoveredEndpointCandidate`` rows and
    persisted to the ``DiscoveredEndpoint`` table so the
    ``internal_route`` adapter can replay them at runtime.
    """
    action = await service.compile(recording_id, registry, llm)

    # ---- Network discovery (Option B) -----------------------------------
    # Real recordings ship with a HAR payload; in the demo we synthesize one
    # from the action name so the discovery pipeline still has something to
    # analyze at compile time.
    rec = await service.fetch(recording_id)
    har = None
    if rec.harCaptured:
        har = _synthesize_demo_har(action.name)

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

    return {
        "action": action.model_dump(mode="json"),
        "discoveredEndpoints": discovered_count,
    }
