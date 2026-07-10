"""Registry module — Multi-tenant action marketplace API (Option C).

Endpoints:
- POST   /registry/tenants              — create a tenant
- GET    /registry/tenants              — list tenants
- POST   /registry/publish              — publish an action to the registry
- GET    /registry/actions              — search published actions
- GET    /registry/actions/{id}         — get a published action
- POST   /registry/actions/{id}/subscribe — subscribe to a published action
- GET    /registry/subscriptions        — list tenant's subscriptions
- POST   /registry/actions/{id}/consume — run a subscribed action (metered)
- GET    /registry/usage                — get usage stats for a tenant
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...api.deps import get_action_registry, get_orchestrator
from ...core.domain.enums import Caller
from ...infrastructure.prisma_repositories import (
    tenant_put, tenant_list, tenant_get_by_slug,
    published_action_put, published_action_list, published_action_get,
    published_action_increment_call,
    subscription_put, subscription_list_by_tenant, subscription_exists,
    usage_event_put, usage_event_stats,
)
from ...shared.ids import new_id

router = APIRouter(prefix="/registry", tags=["registry"])


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #

class CreateTenantBody(BaseModel):
    name: str
    slug: str
    plan: str = "free"


class PublishActionBody(BaseModel):
    actionId: str
    tenantId: str
    visibility: str = "public"
    pricePerCall: float = 0.0


class SubscribeBody(BaseModel):
    subscriberTenantId: str


class ConsumeBody(BaseModel):
    subscriberTenantId: str
    inputs: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Tenants
# --------------------------------------------------------------------------- #

@router.post("/tenants")
async def create_tenant(body: CreateTenantBody) -> dict[str, Any]:
    """Create a new tenant."""
    existing = await tenant_get_by_slug(body.slug)
    if existing:
        raise HTTPException(409, f"Tenant with slug '{body.slug}' already exists")
    tenant = {
        "id": new_id("tenant"),
        "name": body.name,
        "slug": body.slug,
        "plan": body.plan,
        "status": "active",
    }
    await tenant_put(tenant)
    return tenant


@router.get("/tenants")
async def list_tenants() -> dict[str, Any]:
    """List all tenants."""
    tenants = await tenant_list()
    return {"tenants": tenants, "total": len(tenants)}


# --------------------------------------------------------------------------- #
# Published Actions (Registry Catalog)
# --------------------------------------------------------------------------- #

@router.post("/publish")
async def publish_action(
    body: PublishActionBody,
    registry=Depends(get_action_registry),
) -> dict[str, Any]:
    """Publish an action to the shared registry.

    The action becomes discoverable by other tenants who can subscribe to it.
    """
    action = registry.get(body.actionId)
    if action is None:
        raise HTTPException(404, f"Action {body.actionId} not found")

    pub = {
        "id": new_id("pub"),
        "actionId": action.id,
        "tenantId": body.tenantId,
        "name": action.name,
        "signature": action.signature,
        "description": action.description,
        "category": action.category.value if hasattr(action.category, "value") else str(action.category),
        "version": action.version,
        "visibility": body.visibility,
        "pricePerCall": body.pricePerCall,
        "callCount": 0,
        "subscriberCount": 0,
        "status": "active",
    }
    await published_action_put(pub)
    return pub


@router.get("/actions")
async def search_actions(
    q: str | None = Query(None, description="Search query"),
    category: str | None = Query(None),
    visibility: str | None = Query("public"),
) -> dict[str, Any]:
    """Search the public registry of published actions."""
    actions = await published_action_list(
        category=category, visibility=visibility, status="active", q=q)
    return {"actions": actions, "total": len(actions)}


@router.get("/actions/{pub_id}")
async def get_published_action(pub_id: str) -> dict[str, Any]:
    """Get a single published action by id."""
    action = await published_action_get(pub_id)
    if action is None:
        raise HTTPException(404, "Published action not found")
    return action


# --------------------------------------------------------------------------- #
# Subscriptions
# --------------------------------------------------------------------------- #

@router.post("/actions/{pub_id}/subscribe")
async def subscribe(pub_id: str, body: SubscribeBody) -> dict[str, Any]:
    """Subscribe a tenant to a published action.

    The subscriber will use their own credentials at runtime.
    """
    pub = await published_action_get(pub_id)
    if pub is None:
        raise HTTPException(404, "Published action not found")
    if pub["status"] != "active":
        raise HTTPException(400, "Cannot subscribe to a non-active action")

    # Check if already subscribed
    if await subscription_exists(pub_id, body.subscriberTenantId):
        raise HTTPException(409, "Already subscribed")

    sub = {
        "id": new_id("sub"),
        "publishedActionId": pub_id,
        "subscriberTenantId": body.subscriberTenantId,
        "status": "active",
    }
    await subscription_put(sub)
    return sub


@router.get("/subscriptions")
async def list_subscriptions(tenantId: str = Query(...)) -> dict[str, Any]:
    """List a tenant's active subscriptions."""
    subs = await subscription_list_by_tenant(tenantId)
    return {"subscriptions": subs, "total": len(subs)}


# --------------------------------------------------------------------------- #
# Consumption (metered execution)
# --------------------------------------------------------------------------- #

@router.post("/actions/{pub_id}/consume")
async def consume_action(
    pub_id: str,
    body: ConsumeBody,
    registry=Depends(get_action_registry),
    orchestrator=Depends(get_orchestrator),
) -> dict[str, Any]:
    """Run a subscribed action. Uses the subscriber's credentials.

    Generates a UsageEvent for billing. Increments the published action's
    call count.
    """
    pub = await published_action_get(pub_id)
    if pub is None:
        raise HTTPException(404, "Published action not found")

    # Verify subscription
    if not await subscription_exists(pub_id, body.subscriberTenantId):
        raise HTTPException(403, "Tenant is not subscribed to this action")

    # Get the source action
    action = registry.get(pub["actionId"])
    if action is None:
        raise HTTPException(404, "Source action not found in registry")

    # Run the action via the orchestrator
    exe = await orchestrator.run(action, body.inputs, Caller.agent, True)

    # Record usage
    cost_cents = pub["pricePerCall"]
    usage = {
        "id": new_id("usage"),
        "publishedActionId": pub_id,
        "subscriberTenantId": body.subscriberTenantId,
        "executionId": exe.id,
        "status": "success" if exe.status.value == "success" else "failed",
        "costCents": cost_cents,
    }
    await usage_event_put(usage)
    await published_action_increment_call(pub_id)

    return {
        "execution": exe.model_dump(mode="json"),
        "usage": usage,
    }


# --------------------------------------------------------------------------- #
# Usage / Billing
# --------------------------------------------------------------------------- #

@router.get("/usage")
async def get_usage(tenantId: str = Query(...)) -> dict[str, Any]:
    """Get usage stats for a tenant (for billing dashboard)."""
    return await usage_event_stats(tenantId)
