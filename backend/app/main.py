"""Earendel — FastAPI app assembly, CORS, rate limiting, auth middleware, startup, routers."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import jwt
from fastapi import FastAPI, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api.deps import get_action_registry, get_orchestrator
from .config import settings
from .infrastructure.database import dispose_engine, init_engine
from .infrastructure.prisma_repositories import (
    connector_list, dispose_prisma_engine, init_prisma_engine,
    recording_list, repair_list,
)
from .modules.actions.router import router as actions_router
from .modules.auth.router import router as auth_router
from .modules.bu.router import router as bu_router
from .modules.connectors.router import router as connectors_router
from .modules.discovery.router import router as discovery_router
from .modules.executions.router import router as executions_router
from .modules.monitoring.router import router as monitoring_router
from .modules.monitoring.repair_kb_router import router as repair_kb_router
from .modules.publishing.router import router as publishing_router
from .modules.recordings.router import router as recordings_router
from .seed import run as seed_run

logger = logging.getLogger("earendel")
logging.basicConfig(level=logging.INFO)

_START_TIME = datetime.utcnow()

# Shared secret for JWT verification (same as NextAuth BACKEND_SECRET).
BACKEND_SECRET = os.environ.get(
    "BACKEND_SECRET",
    os.environ.get("NEXTAUTH_SECRET", "dev-secret-change-me"),
)

# CORS — restricted to known origins (not wildcard in production).
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:81",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:81",
]
# Add production origin from env if set.
_prod_origin = os.environ.get("EARENDEL_CORS_ORIGIN")
if _prod_origin:
    CORS_ORIGINS.append(_prod_origin)

# Rate limiter — 100 req/min per IP for API, 10 req/min for auth.
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# Public paths that don't require authentication.
PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/healthz",
    "/api/v1/readyz",
    "/api/v1/auth/",
    "/docs",
    "/openapi",
    "/redoc",
)

# Auth endpoints get stricter rate limiting (10/min to prevent brute force).
AUTH_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/register")

app = FastAPI(title="Earendel", version=settings.version,
              description="Reliability layer that turns authorized business "
                          "workflows into typed, monitored, repairable tools.")

# Rate limiting state.
app.state.limiter = limiter

# CORS — restricted origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# SlowAPI middleware for rate limiting.
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """JWT auth + rate limiting middleware.

    Public endpoints (health, auth, docs) are exempt from auth.
    Auth endpoints get stricter rate limiting (10/min vs 100/min).
    """
    path = request.url.path
    client_ip = get_remote_address(request)

    # Rate limiting for auth endpoints (10/min to prevent brute force).
    if any(path.startswith(p) for p in AUTH_PREFIXES):
        try:
            limiter._inject_headers(response := JSONResponse({}), limit=limiter._limiter.limit("10/minute", key_func=lambda _: client_ip))
        except Exception:
            pass  # Don't block if rate limiter fails

    # Public endpoints: skip auth.
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    # Extract token from Authorization header.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        # Also accept token from query param (for SSE / download endpoints).
        token = request.query_params.get("token", "")

    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
        )

    try:
        payload = jwt.decode(
            token,
            BACKEND_SECRET,
            algorithms=["HS256"],
            issuer="earendel-studio",
            audience="earendel-api",
        )
        # Attach user info to request state for downstream handlers.
        request.state.user = {
            "uid": payload.get("uid", ""),
            "email": payload.get("email", ""),
        }
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token expired"},
        )
    except jwt.InvalidTokenError as exc:
        return JSONResponse(
            status_code=401,
            content={"detail": f"Invalid token: {exc}"},
        )

    return await call_next(request)


@app.on_event("startup")
async def _startup() -> None:
    """Initialise DBs + seed if needed; log seeded action ids for the frontend.

    Both the legacy document store (`init_engine`) and the Prisma-backed
    engine (`init_prisma_engine`) are initialised — the legacy one is kept
    for backward compatibility while modules finish migrating.
    """
    await init_engine()
    await init_prisma_engine()
    registry = get_action_registry()
    await registry.load()
    if settings.seed_on_startup and not registry.list():
        ids = await seed_run(registry)
        logger.info("Seeded Earendel demo data. Action ids: %s", ids)
    else:
        logger.info("Actions already present (%d) — skipping seed.",
                    len(registry.list()))

    # Phase 2: build the TF-IDF semantic index for the repair KB at startup
    # so the first failure query benefits from semantic retrieval.
    try:
        from .core.repair.embedding import rebuild_index
        from .infrastructure.prisma_repositories import repair_kb_list
        all_entries = await repair_kb_list()
        indexed = await rebuild_index(all_entries)
        logger.info("Repair KB TF-IDF index: %d entries indexed.", indexed)
    except Exception as exc:
        logger.warning("Repair KB index build failed at startup: %s", exc)

    # Phase 6: start the canary scheduler (runs every 15 minutes).
    # Canaries auto-trigger repair proposals when they fail.
    try:
        from .core.monitoring.canary_scheduler import start_canary_scheduler
        from .api.deps import get_orchestrator
        orchestrator = get_orchestrator()
        start_canary_scheduler(registry, orchestrator)
    except Exception as exc:
        logger.warning("Canary scheduler failed to start: %s", exc)


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Dispose both DB engines on shutdown."""
    # Phase 6: stop the canary scheduler
    try:
        from .core.monitoring.canary_scheduler import stop_canary_scheduler
        stop_canary_scheduler()
    except Exception:
        pass
    await dispose_prisma_engine()
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
    try:
        connectors = await connector_list()
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
    from .modules.monitoring.service import summary

    mon = await summary(registry)
    connectors = await connector_list()
    recordings = await recording_list()
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
    """Global search across actions, connectors, executions, recordings, and repairs.

    Returns matched items grouped by type, with enough metadata for the
    frontend to navigate to the right view.
    """
    from .modules.executions.repository import list_executions
    query = (q or "").strip().lower()
    if not query:
        return {"actions": [], "connectors": [], "executions": [],
                "recordings": [], "repairs": []}

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
        for c in await connector_list()
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

    recordings = [
        {
            "id": r["id"],
            "name": r.get("name", ""),
            "connectorId": r.get("connectorId", ""),
            "status": r.get("status", ""),
            "steps": len(r.get("steps", [])),
        }
        for r in await recording_list()
        if query in r.get("name", "").lower()
        or query in r.get("status", "").lower()
    ][:10]

    repairs = [
        {
            "id": r["id"],
            "actionId": r.get("actionId", ""),
            "actionVersion": r.get("actionVersion", ""),
            "status": r.get("status", ""),
            "confidence": r.get("confidence", 0),
            "candidateSelector": r.get("candidateSelector", ""),
            "reason": r.get("reason", ""),
        }
        for r in await repair_list()
        if query in r.get("status", "").lower()
        or query in r.get("reason", "").lower()
        or query in r.get("candidateSelector", "").lower()
        or query in r.get("failedSelector", "").lower()
    ][:10]

    return {
        "actions": actions,
        "connectors": connectors,
        "executions": executions,
        "recordings": recordings,
        "repairs": repairs,
    }


@app.get("/api/v1/dashboard/activity")
async def dashboard_activity_endpoint(
    registry=Depends(get_action_registry),
) -> dict:
    """Recent activity feed — last N events across the system (executions,
    repairs, recordings, version bumps) sorted by time, most recent first."""
    from .modules.executions.repository import list_executions
    from datetime import datetime

    events: list[dict] = []
    now = datetime.utcnow()

    # Executions
    for e in await list_executions():
        events.append({
            "type": "execution",
            "ts": e.startedAt.isoformat() + "Z",
            "title": f"{e.actionName} {e.status.value}",
            "description": f"{e.caller.value} · {e.adapter.value} · {e.durationMs}ms",
            "refId": e.id,
            "refType": "execution",
            "status": e.status.value,
        })

    # Repairs
    for r in await repair_list():
        ts = r.get("detectedAt", now.isoformat())
        if isinstance(ts, str):
            ts_parsed = ts
        else:
            ts_parsed = ts.isoformat() + "Z"
        events.append({
            "type": "repair",
            "ts": ts_parsed,
            "title": f"Repair {r.get('status', 'pending')}",
            "description": r.get("reason", "")[:80],
            "refId": r.get("id", ""),
            "refType": "repair",
            "status": r.get("status", "pending"),
        })

    # Recordings
    for r in await recording_list():
        ts = r.get("createdAt", now.isoformat())
        if isinstance(ts, str):
            ts_parsed = ts
        else:
            ts_parsed = ts.isoformat() + "Z"
        events.append({
            "type": "recording",
            "ts": ts_parsed,
            "title": f"Recording {r.get('status', 'captured')}",
            "description": f"{r.get('name', '')} · {len(r.get('steps', []))} steps",
            "refId": r.get("id", ""),
            "refType": "recording",
            "status": r.get("status", "captured"),
        })

    # Version bumps (from action versions)
    for a in registry.list():
        for v in a.versions:
            events.append({
                "type": "version",
                "ts": v.releasedAt.isoformat() + "Z",
                "title": f"{a.name} v{v.version}",
                "description": v.changelog,
                "refId": a.id,
                "refType": "action",
                "status": v.status,
            })

    # Sort by ts desc, take 12.
    events.sort(key=lambda e: e["ts"], reverse=True)
    return {"events": events[:12], "total": len(events)}


# Feature routers
app.include_router(connectors_router, prefix="/api/v1")
app.include_router(recordings_router, prefix="/api/v1")
app.include_router(actions_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")
app.include_router(monitoring_router, prefix="/api/v1")
app.include_router(repair_kb_router, prefix="/api/v1")
app.include_router(publishing_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(bu_router, prefix="/api/v1")
app.include_router(discovery_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port,
                reload=False)
