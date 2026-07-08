"""Earendel — FastAPI app assembly, CORS, startup, routers."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .api.deps import get_action_registry, get_orchestrator
from .config import settings
from .infrastructure.database import dispose_engine, init_engine
from .modules.actions.router import router as actions_router
from .modules.auth.router import router as auth_router
from .modules.connectors.router import router as connectors_router
from .modules.executions.router import router as executions_router
from .modules.monitoring.router import router as monitoring_router
from .modules.publishing.router import router as publishing_router
from .modules.recordings.router import router as recordings_router
from .seed import run as seed_run

logger = logging.getLogger("earendel")
logging.basicConfig(level=logging.INFO)

_START_TIME = datetime.utcnow()

app = FastAPI(title="Earendel", version=settings.version,
              description="Reliability layer that turns authorized business "
                          "workflows into typed, monitored, repairable tools.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    """Initialise DB + seed if needed; log seeded action ids for the frontend."""
    await init_engine()
    registry = get_action_registry()
    await registry.load()
    if settings.seed_on_startup and not registry.list():
        ids = await seed_run(registry)
        logger.info("Seeded Earendel demo data. Action ids: %s", ids)
    else:
        logger.info("Actions already present (%d) — skipping seed.",
                    len(registry.list()))


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Dispose the DB engine on shutdown."""
    await dispose_engine()


@app.get("/api/v1/health")
async def health() -> dict:
    """Liveness probe."""
    uptime = (datetime.utcnow() - _START_TIME).total_seconds()
    return {"status": "ok", "version": settings.version, "uptime": uptime}


@app.get("/api/v1/healthz")
async def healthz() -> dict:
    """Liveness probe (Kubernetes-style). Always returns 200 if the process is up."""
    return {"status": "alive"}


@app.get("/api/v1/readyz")
async def readyz(registry=Depends(get_action_registry)) -> dict:
    """Readiness probe — checks the DB + action registry are initialised."""
    from .infrastructure.database import doc_list
    try:
        connectors = await doc_list("connectors")
        actions = registry.list()
        return {
            "status": "ready",
            "checks": {
                "database": "ok",
                "action_registry": "ok" if actions else "empty",
            },
            "counts": {
                "connectors": len(connectors),
                "actions": len(actions),
            },
        }
    except Exception as exc:
        return {
            "status": "not_ready",
            "checks": {"database": f"error: {exc}"},
        }


@app.get("/api/v1/dashboard/stats")
async def dashboard_stats(registry=Depends(get_action_registry)) -> dict:
    """Studio dashboard aggregates — shape matches the frontend DashboardStats type."""
    from .infrastructure.database import doc_list
    from .modules.monitoring.service import summary

    mon = await summary(registry)
    connectors = await doc_list("connectors")
    recordings = await doc_list("recordings")
    actions = registry.list()
    published = [a for a in actions if a.status.value == "published"]

    return {
        "connectors": len(connectors),
        "recordings": len(recordings),
        "publishedActions": len(published),
        "executionsToday": mon.get("executions24h", 0),
        "successRate": round(mon.get("successRate24h", 0), 3),
        "openRepairs": mon.get("openRepairs", 0),
        "canaryCoverage": round(mon.get("canaryPassRate", 0), 3),
    }


@app.get("/api/v1/search")
async def search_endpoint(
    q: str,
    registry=Depends(get_action_registry),
) -> dict:
    """Global search across actions, connectors, and executions.

    Returns matched items grouped by type, with enough metadata for the
    frontend to navigate to the right view.
    """
    from .infrastructure.database import doc_list
    from .modules.executions.repository import list_executions
    query = (q or "").strip().lower()
    if not query:
        return {"actions": [], "connectors": [], "executions": []}

    actions = [
        {
            "id": a.id,
            "name": a.name,
            "signature": a.signature,
            "description": a.description,
            "category": a.category.value,
            "status": a.status.value,
            "version": a.version,
        }
        for a in registry.list()
        if query in a.name.lower()
        or query in a.signature.lower()
        or query in a.description.lower()
        or query in a.category.value.lower()
    ][:10]

    connectors = [
        {
            "id": c["id"],
            "name": c["name"],
            "targetApp": c.get("targetApp", ""),
            "targetDomain": c.get("targetDomain", ""),
            "category": c.get("category", ""),
            "status": c.get("status", ""),
        }
        for c in await doc_list("connectors")
        if query in c.get("name", "").lower()
        or query in c.get("targetApp", "").lower()
        or query in c.get("targetDomain", "").lower()
        or query in c.get("category", "").lower()
    ][:10]

    exe_all = await list_executions()
    executions = [
        {
            "id": e.id,
            "actionId": e.actionId,
            "actionName": e.actionName,
            "status": e.status.value,
            "adapter": e.adapter.value,
            "caller": e.caller.value,
            "durationMs": e.durationMs,
        }
        for e in exe_all
        if query in e.actionName.lower()
        or query in e.status.value.lower()
        or query in e.adapter.value.lower()
        or query in e.caller.value.lower()
        or any(query in str(v).lower() for v in e.inputs.values())
    ][:10]

    return {"actions": actions, "connectors": connectors, "executions": executions}


# Feature routers
app.include_router(connectors_router, prefix="/api/v1")
app.include_router(recordings_router, prefix="/api/v1")
app.include_router(actions_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")
app.include_router(monitoring_router, prefix="/api/v1")
app.include_router(publishing_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port,
                reload=False)
