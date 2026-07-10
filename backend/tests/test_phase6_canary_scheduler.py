"""Tests for Phase 6 — Real Canary Scheduler.

Tests that:
1. run_all_canaries runs canaries for published/testing actions
2. run_all_canaries skips draft/broken actions
3. run_all_canaries persists executions
4. run_all_canaries auto-triggers repair proposer on selector failures
5. start_canary_scheduler creates a scheduler with the right interval
6. stop_canary_scheduler stops the scheduler
7. get_scheduler_status returns the correct status
8. timeseries no longer has synthetic baseline data
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.domain.entities import (
    TypedAction, ActionContract, FieldSchema, Execution, TraceEvent,
)
from app.core.domain.value_objects import FieldSchema as FieldSchemaVO
from app.core.domain.enums import (
    AdapterType, Caller, RiskLevel, PermissionScope, WorkflowCategory,
    ActionStatus, ExecutionStatus,
)
from app.core.monitoring.canary_scheduler import (
    run_all_canaries,
    start_canary_scheduler,
    stop_canary_scheduler,
    get_scheduler_status,
    DEFAULT_INTERVAL_MINUTES,
)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

def _make_action(
    name: str = "testAction",
    status: ActionStatus = ActionStatus.testing,
) -> TypedAction:
    return TypedAction(
        id=f"act_canary_{name}",
        connectorId="conn_test",
        name=name,
        signature=f"{name}(id: string)",
        description="test action",
        category=WorkflowCategory.finance,
        contract=ActionContract(
            name=name,
            inputs=[FieldSchemaVO(name="id", type="string", required=True, default="test-001")],
            outputs=[FieldSchemaVO(name="result", type="string", required=True)],
        ),
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.api],
        preferredAdapter=AdapterType.api,
        status=status,
    )


def _make_execution(
    action_id: str,
    status: ExecutionStatus = ExecutionStatus.success,
    error_message: str | None = None,
) -> Execution:
    return Execution(
        id=f"exe_canary_{action_id}",
        actionId=action_id,
        actionName="testAction",
        caller=Caller.canary,
        inputs={"id": "test-001"},
        outputs={"result": "ok"},
        adapter=AdapterType.api,
        fallbackChain=[AdapterType.api],
        status=status,
        durationMs=100,
        startedAt=datetime.utcnow(),
        finishedAt=datetime.utcnow(),
        traces=[],
        screenshots=[],
        postconditionsMet=True,
        errorMessage=error_message,
        riskApproved=True,
    )


class MockRegistry:
    """Mock action registry with a list of actions."""
    def __init__(self, actions: list[TypedAction]):
        self._actions = actions

    def list(self):
        return self._actions


# --------------------------------------------------------------------------- #
# 1. run_all_canaries                                                          #
# --------------------------------------------------------------------------- #

class TestRunAllCanaries:
    """Tests for the run_all_canaries function."""

    @pytest.mark.asyncio
    async def test_runs_canary_for_testing_actions(self, seeded_db):
        """Should run canaries for actions with status=testing."""
        action = _make_action("testAction1", ActionStatus.testing)
        registry = MockRegistry([action])

        mock_orchestrator = MagicMock()
        mock_execution = _make_execution(action.id, ExecutionStatus.success)
        mock_orchestrator.run = AsyncMock(return_value=mock_execution)

        with patch("app.modules.executions.repository.put_execution", new_callable=AsyncMock):
            result = await run_all_canaries(registry, mock_orchestrator)

        assert result["total"] == 1
        assert result["succeeded"] == 1
        assert result["failed"] == 0
        mock_orchestrator.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_runs_canary_for_published_actions(self, seeded_db):
        """Should run canaries for actions with status=published."""
        action = _make_action("publishedAction", ActionStatus.published)
        registry = MockRegistry([action])

        mock_orchestrator = MagicMock()
        mock_execution = _make_execution(action.id, ExecutionStatus.success)
        mock_orchestrator.run = AsyncMock(return_value=mock_execution)

        with patch("app.modules.executions.repository.put_execution", new_callable=AsyncMock):
            result = await run_all_canaries(registry, mock_orchestrator)

        assert result["total"] == 1
        assert result["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_skips_draft_actions(self, seeded_db):
        """Should NOT run canaries for actions with status=draft."""
        action = _make_action("draftAction", ActionStatus.draft)
        registry = MockRegistry([action])

        mock_orchestrator = MagicMock()
        mock_orchestrator.run = AsyncMock()

        result = await run_all_canaries(registry, mock_orchestrator)

        assert result["total"] == 0
        mock_orchestrator.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_counts_failures(self, seeded_db):
        """Should count failed canaries."""
        action = _make_action("failingAction", ActionStatus.testing)
        registry = MockRegistry([action])

        mock_orchestrator = MagicMock()
        mock_execution = _make_execution(action.id, ExecutionStatus.failed, "some error")
        mock_orchestrator.run = AsyncMock(return_value=mock_execution)

        with patch("app.modules.executions.repository.put_execution", new_callable=AsyncMock):
            result = await run_all_canaries(registry, mock_orchestrator)

        assert result["total"] == 1
        assert result["failed"] == 1
        assert result["succeeded"] == 0

    @pytest.mark.asyncio
    async def test_auto_triggers_repair_on_selector_failure(self, seeded_db):
        """Should auto-trigger repair proposer when a canary fails with a selector error."""
        action = _make_action("selectorFailAction", ActionStatus.testing)
        registry = MockRegistry([action])

        mock_orchestrator = MagicMock()
        mock_execution = _make_execution(
            action.id, ExecutionStatus.failed,
            "selector not found: button[data-testid='download']",
        )
        mock_orchestrator.run = AsyncMock(return_value=mock_execution)

        # Mock the repair proposer to return a proposal
        mock_proposal = MagicMock()
        mock_proposal.model_dump.return_value = {"id": "rep_test"}
        mock_proposal.candidateSelector = "button[aria-label='Download']"
        mock_proposal.confidence = 0.88

        with patch("app.modules.executions.repository.put_execution", new_callable=AsyncMock), \
             patch("app.modules.monitoring.repository.repair_put", new_callable=AsyncMock), \
             patch("app.core.repair.repair_proposer.propose", new_callable=AsyncMock, return_value=mock_proposal):
            result = await run_all_canaries(registry, mock_orchestrator)

        assert result["repairs_proposed"] == 1

    @pytest.mark.asyncio
    async def test_no_repair_proposal_on_non_selector_failure(self, seeded_db):
        """Should NOT trigger repair proposer for non-selector failures."""
        action = _make_action("nonSelectorFail", ActionStatus.testing)
        registry = MockRegistry([action])

        mock_orchestrator = MagicMock()
        mock_execution = _make_execution(
            action.id, ExecutionStatus.failed, "HTTP 500 internal server error",
        )
        mock_orchestrator.run = AsyncMock(return_value=mock_execution)

        with patch("app.modules.executions.repository.put_execution", new_callable=AsyncMock), \
             patch("app.core.repair.repair_proposer.propose", new_callable=AsyncMock) as mock_propose:
            result = await run_all_canaries(registry, mock_orchestrator)

        assert result["repairs_proposed"] == 0
        mock_propose.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_empty_registry(self, seeded_db):
        """Should return zero summary when registry is empty."""
        registry = MockRegistry([])
        mock_orchestrator = MagicMock()

        result = await run_all_canaries(registry, mock_orchestrator)

        assert result["total"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_handles_orchestrator_exception(self, seeded_db):
        """Should count as failure when the orchestrator raises."""
        action = _make_action("exceptionAction", ActionStatus.testing)
        registry = MockRegistry([action])

        mock_orchestrator = MagicMock()
        mock_orchestrator.run = AsyncMock(side_effect=Exception("orchestrator crashed"))

        result = await run_all_canaries(registry, mock_orchestrator)

        assert result["total"] == 1
        assert result["failed"] == 1


# --------------------------------------------------------------------------- #
# 2. Scheduler lifecycle                                                       #
# --------------------------------------------------------------------------- #

class TestSchedulerLifecycle:
    """Tests for start/stop/status of the canary scheduler."""

    @pytest.mark.asyncio
    async def test_start_and_stop_scheduler(self):
        """Should start and stop the scheduler."""
        action = _make_action("schedTest", ActionStatus.testing)
        registry = MockRegistry([action])
        mock_orchestrator = MagicMock()

        scheduler = start_canary_scheduler(registry, mock_orchestrator, interval_minutes=1)
        assert scheduler.running

        status = get_scheduler_status()
        assert status["running"] is True

        stop_canary_scheduler()
        status = get_scheduler_status()
        assert status["running"] is False

    @pytest.mark.asyncio
    async def test_scheduler_status_when_not_running(self):
        """Should return running=False when scheduler hasn't been started."""
        stop_canary_scheduler()  # Ensure stopped
        status = get_scheduler_status()
        assert status["running"] is False
        assert status["nextRun"] is None

    @pytest.mark.asyncio
    async def test_start_scheduler_is_idempotent(self):
        """Starting twice should replace the existing scheduler."""
        action = _make_action("idempotentTest", ActionStatus.testing)
        registry = MockRegistry([action])
        mock_orchestrator = MagicMock()

        start_canary_scheduler(registry, mock_orchestrator, interval_minutes=1)
        start_canary_scheduler(registry, mock_orchestrator, interval_minutes=2)

        status = get_scheduler_status()
        assert status["running"] is True

        stop_canary_scheduler()

    def test_default_interval_is_15_minutes(self):
        """DEFAULT_INTERVAL_MINUTES should be 15."""
        assert DEFAULT_INTERVAL_MINUTES == 15


# --------------------------------------------------------------------------- #
# 3. Timeseries (no synthetic data)                                            #
# --------------------------------------------------------------------------- #

class TestTimeseriesNoSynthetic:
    """Tests that the timeseries no longer injects synthetic baseline data."""

    @pytest.mark.asyncio
    async def test_timeseries_returns_real_data_only(self, seeded_db):
        """The timeseries should show only real execution data, no synthetic baseline."""
        from app.modules.monitoring.timeseries_service import timeseries

        result = await timeseries(hours=24)
        points = result["points"]

        # All 24 hourly buckets should be present
        assert len(points) == 24

        # Before any real canary executions, the totals should be 0 (or very low)
        # NOT the old synthetic baseline of 4-9 per hour.
        # At least the first few hours (oldest) should have total=0 if no
        # executions happened that long ago.
        totals = [p["total"] for p in points]
        # The sum of totals should NOT be 24*4=96 (the old synthetic minimum).
        # With real data only, it should be much lower (only real executions).
        assert sum(totals) < 96, \
            f"totals sum {sum(totals)} suggests synthetic baseline is still present"

    @pytest.mark.asyncio
    async def test_timeseries_empty_hours_show_success_rate_1(self, seeded_db):
        """Hours with no executions should show successRate=1.0 (not 0.0)."""
        from app.modules.monitoring.timeseries_service import timeseries

        result = await timeseries(hours=24)
        points = result["points"]

        for p in points:
            if p["total"] == 0:
                assert p["successRate"] == 1.0, \
                    "empty hours should show successRate=1.0 (no failures)"
                assert p["failures"] == 0
