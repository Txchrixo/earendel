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
