"""Shared test fixtures for the Earendel backend pytest suite.

Provides:
  - ``client``: an ``httpx.AsyncClient`` bound to the FastAPI app via
    ``ASGITransport`` (with a seeded DB).
  - ``auth_token`` / ``auth_headers``: a valid JWT minted with the same
    ``BACKEND_SECRET`` the app's auth middleware verifies against.
  - ``sample_action``: a hand-built ``TypedAction`` (downloadInvoice-shaped).
  - ``sample_execution``: a hand-built ``Execution`` of that action.
  - ``adapter_ctx``: a minimal ``ExecutionContext`` for direct adapter tests.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

# ---- Env defaults (must be set BEFORE any ``app.*`` import) ----
# Keep the demo mode on so the BrowserAdapter uses its simulation path.
os.environ.setdefault("EARENDEL_DEMO_MODE", "true")
# Use a dedicated test DB so the dev DB is never mutated by the suite.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = _BACKEND_ROOT / "earendel-test.db"
os.environ.setdefault(
    "EARENDEL_DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB}"
)
# Dedicated Prisma test DB — isolated from the production custom.db so the
# suite can reset it freely. The schema is created on init by SQLAlchemy.
_TEST_PRISMA_DB = _BACKEND_ROOT / "earendel-prisma-test.db"
os.environ.setdefault("EARENDEL_PRISMA_DB", str(_TEST_PRISMA_DB))
# Make the backend package importable.
sys.path.insert(0, str(_BACKEND_ROOT))

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings  # noqa: E402  — ensures settings load test env
from app.main import BACKEND_SECRET, app  # noqa: E402
from app.api.deps import get_action_registry  # noqa: E402
from app.infrastructure.database import dispose_engine, init_engine  # noqa: E402
from app.infrastructure.prisma_repositories import (  # noqa: E402
    dispose_prisma_engine, init_prisma_engine,
)
from app.seed import run as seed_run  # noqa: E402

from app.adapters.base import ExecutionContext  # noqa: E402
from app.core.domain.entities import (  # noqa: E402
    ActionContract,
    ActionVersion,
    Execution,
    TraceEvent,
    TypedAction,
)
from app.core.domain.enums import (  # noqa: E402
    ActionStatus,
    AdapterType,
    Caller,
    ExecutionStatus,
    PermissionScope,
    RiskLevel,
    WorkflowCategory,
)
from app.core.domain.value_objects import FieldSchema  # noqa: E402
from app.infrastructure.telemetry import TraceCollector  # noqa: E402
from app.infrastructure.vault import CredentialVault  # noqa: E402


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def mint_jwt(secret: str = BACKEND_SECRET) -> str:
    """Mint a JWT the auth middleware will accept (HS256, iss/aud matching)."""
    now = datetime.utcnow()
    payload = {
        "uid": "usr_testfixture",
        "email": "test@earendel.io",
        "iss": "earendel-studio",
        "aud": "earendel-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def auth_token() -> str:
    """A valid JWT signed with the backend's secret."""
    return mint_jwt()


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Authorization headers carrying a valid JWT."""
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Database + seeded app + httpx AsyncClient
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_db() -> AsyncIterator[None]:
    """Initialise the test DB engine and seed demo data once per test."""
    # Reset both test DB files so each test session starts clean.
    for p in (_TEST_DB, _TEST_PRISMA_DB):
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    # The prisma engine caches _engine at module level; force a fresh init
    # after deleting the test DB file by disposing first.
    await dispose_prisma_engine()
    await init_engine()
    await init_prisma_engine()
    registry = get_action_registry()
    # The ActionRegistry is an @lru_cache singleton — clear its in-memory
    # index so re-seeding from the fresh DB works.
    registry._by_id.clear()
    await registry.load()
    if not registry.list():
        await seed_run(registry)
    yield
    await dispose_prisma_engine()
    await dispose_engine()


@pytest_asyncio.fixture
async def client(seeded_db: None) -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient bound to the FastAPI app via ASGITransport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Domain-object fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_contract() -> ActionContract:
    """An invoice-shaped ActionContract used by validation + adapter tests."""
    return ActionContract(
        inputs=[FieldSchema("invoiceId", "string", True, "Supplier invoice id")],
        outputs=[
            FieldSchema("invoiceNumber", "string", True, "Invoice number"),
            FieldSchema("pdfUrl", "url", True, "Downloaded PDF URL"),
            FieldSchema("supplierName", "string", True, "Supplier name"),
            FieldSchema("amount", "number", True, "Invoice total"),
            FieldSchema(
                "status", "string", True, "Payment status",
                enum=("paid", "pending", "overdue"),
            ),
        ],
        preconditions=["connector active", "credentials valid"],
        postconditions=["pdf downloaded", "amount > 0", "status present"],
    )


@pytest.fixture
def sample_action(sample_contract: ActionContract) -> TypedAction:
    """A hand-built downloadInvoice TypedAction with three version entries."""
    now = datetime.utcnow()
    return TypedAction(
        id="act_test_downloadInvoice",
        connectorId="conn_test_stripe",
        name="downloadInvoice",
        signature="downloadInvoice(invoiceId: string)",
        description="Download an invoice via the Stripe API (test mode).",
        category=WorkflowCategory.finance,
        contract=sample_contract,
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.api, AdapterType.internal_route, AdapterType.browser],
        preferredAdapter=AdapterType.api,
        status=ActionStatus.published,
        version="1.2.0",
        versions=[
            ActionVersion(
                version="1.0.0", releasedAt=now - timedelta(days=14),
                changelog="initial compile", adapter=AdapterType.api,
                successRate=0.91, status="stable",
            ),
            ActionVersion(
                version="1.1.0", releasedAt=now - timedelta(days=7),
                changelog="added retry on timeout", adapter=AdapterType.api,
                successRate=0.95, status="stable",
            ),
            ActionVersion(
                version="1.2.0", releasedAt=now,
                changelog="selector hardened after repair", adapter=AdapterType.api,
                successRate=0.98, status="latest",
            ),
        ],
    )


@pytest.fixture
def sample_execution(sample_action: TypedAction) -> Execution:
    """A hand-built successful Execution of ``sample_action``."""
    now = datetime.utcnow()
    return Execution(
        id="exe_test_0001",
        actionId=sample_action.id,
        actionName=sample_action.name,
        caller=Caller.agent,
        inputs={"invoiceId": "INV-1001"},
        outputs={
            "invoiceNumber": "INV-1001",
            "pdfUrl": "https://files.acme.com/invoices/INV-1001.pdf",
            "supplierName": "Acme Supplies GmbH",
            "amount": 4280.50,
            "status": "paid",
        },
        adapter=AdapterType.api,
        fallbackChain=[AdapterType.api, AdapterType.internal_route, AdapterType.browser],
        status=ExecutionStatus.success,
        durationMs=120,
        startedAt=now,
        finishedAt=now + timedelta(seconds=1),
        traces=[
            TraceEvent(
                ts=now, adapter=AdapterType.api, level="info",
                message="GET https://api.stripe.com/v1/invoices?limit=5",
                step="http.request", durationMs=40,
            ),
            TraceEvent(
                ts=now, adapter=AdapterType.api, level="info",
                message="200 OK (120ms)", step="http.response", durationMs=80,
            ),
        ],
    )


@pytest.fixture
def failed_execution(sample_action: TypedAction) -> Execution:
    """A hand-built Execution that failed with a selector error.

    Used by ``test_repair_proposer.py`` to exercise the selector-healing path.
    """
    now = datetime.utcnow()
    return Execution(
        id="exe_test_failed_0001",
        actionId=sample_action.id,
        actionName=sample_action.name,
        caller=Caller.agent,
        inputs={"invoiceId": "INV-9999"},
        outputs=None,
        adapter=AdapterType.browser,
        fallbackChain=[AdapterType.api, AdapterType.browser],
        status=ExecutionStatus.failed,
        durationMs=900,
        startedAt=now,
        finishedAt=now + timedelta(seconds=1),
        traces=[
            TraceEvent(
                ts=now, adapter=AdapterType.browser, level="error",
                message='selector not found: button[data-testid="download-btn"]',
                step="click", durationMs=380,
            ),
        ],
        errorMessage='selector not found: button[data-testid="download-btn"]',
    )


@pytest.fixture
def adapter_ctx() -> ExecutionContext:
    """A minimal ExecutionContext for direct adapter unit tests."""
    return ExecutionContext(
        caller=Caller.agent,
        risk_approved=True,
        run_id="run_testfixture",
        vault=CredentialVault(),
        telemetry=TraceCollector(),
    )
