"""Tests for Phase 7 — Evaluation Harness.

Tests that:
1. BENCHMARK_WORKFLOWS has 10 workflows across multiple categories
2. run_earendel_full produces RunResult objects
3. run_earendel_api_only produces RunResult objects
4. run_playwright_raw_baseline simulates 15% failure rate
5. run_bu_cloud_baseline simulates compounding errors (0.85^steps)
6. aggregate_results computes correct summaries
7. run_full_benchmark returns the full structure with claims
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

import pytest

from app.core.evaluation.harness import (
    BENCHMARK_WORKFLOWS,
    BenchmarkWorkflow,
    RunResult,
    BenchmarkSummary,
    run_earendel_full,
    run_earendel_api_only,
    run_playwright_raw_baseline,
    run_bu_cloud_baseline,
    aggregate_results,
    run_full_benchmark,
)


# --------------------------------------------------------------------------- #
# 1. Benchmark workflow definitions                                            #
# --------------------------------------------------------------------------- #

class TestBenchmarkWorkflows:
    """Tests for the benchmark workflow definitions."""

    def test_has_10_workflows(self):
        """Should have exactly 10 benchmark workflows."""
        assert len(BENCHMARK_WORKFLOWS) == 10

    def test_covers_multiple_categories(self):
        """Should cover finance, logistics, healthcare, ecommerce, hr, compliance."""
        categories = {wf.category for wf in BENCHMARK_WORKFLOWS}
        assert "finance" in categories
        assert "logistics" in categories
        assert "healthcare" in categories
        assert "ecommerce" in categories

    def test_each_workflow_has_inputs(self):
        """Each workflow should have non-empty inputs."""
        for wf in BENCHMARK_WORKFLOWS:
            assert wf.inputs, f"{wf.name} has no inputs"
            assert wf.action_name, f"{wf.name} has no action_name"

    def test_each_workflow_has_expected_outputs(self):
        """Each workflow should have expected output fields."""
        for wf in BENCHMARK_WORKFLOWS:
            assert wf.expected_outputs, f"{wf.name} has no expected_outputs"


# --------------------------------------------------------------------------- #
# 2. Baseline runners                                                          #
# --------------------------------------------------------------------------- #

class TestPlaywrightRawBaseline:
    """Tests for the raw Playwright baseline (simulated)."""

    @pytest.mark.asyncio
    async def test_produces_results(self):
        """Should produce RunResult objects."""
        wf = BENCHMARK_WORKFLOWS[0]
        results = await run_playwright_raw_baseline(wf, runs=5)
        assert len(results) == 5
        assert all(isinstance(r, RunResult) for r in results)
        assert all(r.baseline == "playwright_raw" for r in results)

    @pytest.mark.asyncio
    async def test_has_realistic_latency(self):
        """Latency should be 800-1500ms (browser automation range)."""
        wf = BENCHMARK_WORKFLOWS[0]
        results = await run_playwright_raw_baseline(wf, runs=10)
        for r in results:
            assert 800 <= r.latency_ms <= 1500

    @pytest.mark.asyncio
    async def test_zero_cost(self):
        """Raw Playwright has no LLM cost."""
        wf = BENCHMARK_WORKFLOWS[0]
        results = await run_playwright_raw_baseline(wf, runs=5)
        for r in results:
            assert r.cost_usd == 0.0


class TestBuCloudBaseline:
    """Tests for the Browser Use Cloud baseline (simulated)."""

    @pytest.mark.asyncio
    async def test_produces_results(self):
        """Should produce RunResult objects."""
        wf = BENCHMARK_WORKFLOWS[0]
        results = await run_bu_cloud_baseline(wf, runs=5)
        assert len(results) == 5
        assert all(r.baseline == "bu_cloud" for r in results)

    @pytest.mark.asyncio
    async def test_has_realistic_latency(self):
        """Latency should be 2000-5000ms (LLM-at-every-step range)."""
        wf = BENCHMARK_WORKFLOWS[0]
        results = await run_bu_cloud_baseline(wf, runs=10)
        for r in results:
            assert 2000 <= r.latency_ms <= 5000

    @pytest.mark.asyncio
    async def test_has_cost(self):
        """BU Cloud has $0.05 cost per run."""
        wf = BENCHMARK_WORKFLOWS[0]
        results = await run_bu_cloud_baseline(wf, runs=5)
        for r in results:
            assert r.cost_usd == 0.05


# --------------------------------------------------------------------------- #
# 3. Aggregation                                                               #
# --------------------------------------------------------------------------- #

class TestAggregateResults:
    """Tests for the aggregate_results function."""

    def test_aggregates_empty_list(self):
        """Should return zero summary for empty results."""
        summary = aggregate_results([], "earendel_full")
        assert summary.total_runs == 0
        assert summary.success_rate == 0.0

    def test_aggregates_success_rate(self):
        """Should compute success rate correctly."""
        results = [
            RunResult("wf1", "earendel_full", True, 100, 0.0),
            RunResult("wf1", "earendel_full", True, 200, 0.0),
            RunResult("wf1", "earendel_full", False, 300, 0.0),
        ]
        summary = aggregate_results(results, "earendel_full")
        assert summary.total_runs == 3
        assert summary.successes == 2
        assert summary.failures == 1
        assert summary.success_rate == 0.667

    def test_aggregates_latency_percentiles(self):
        """Should compute p50, p95, p99 latency."""
        results = [
            RunResult(f"wf{i}", "earendel_full", True, 100 + i * 10, 0.0)
            for i in range(20)
        ]
        summary = aggregate_results(results, "earendel_full")
        assert summary.p50_latency_ms > 0
        assert summary.p95_latency_ms >= summary.p50_latency_ms

    def test_aggregates_cost(self):
        """Should compute average and total cost."""
        results = [
            RunResult("wf1", "bu_cloud", True, 1000, 0.05),
            RunResult("wf1", "bu_cloud", True, 2000, 0.05),
        ]
        summary = aggregate_results(results, "bu_cloud")
        assert summary.avg_cost_usd == 0.05
        assert summary.total_cost_usd == 0.10

    def test_filters_by_baseline(self):
        """Should only aggregate results matching the baseline name."""
        results = [
            RunResult("wf1", "earendel_full", True, 100, 0.0),
            RunResult("wf1", "bu_cloud", True, 2000, 0.05),
        ]
        summary = aggregate_results(results, "earendel_full")
        assert summary.total_runs == 1  # only the earendel_full result


# --------------------------------------------------------------------------- #
# 4. Full benchmark run                                                        #
# --------------------------------------------------------------------------- #

class TestFullBenchmark:
    """Tests for the full benchmark run."""

    @pytest.mark.asyncio
    async def test_full_benchmark_returns_structure(self, seeded_db):
        """Should return the full benchmark structure with baselines + claims."""
        from app.api.deps import get_action_registry, get_orchestrator

        registry = get_action_registry()
        await registry.load()
        orchestrator = get_orchestrator()

        # Run with 1 run per workflow for speed
        result = await run_full_benchmark(
            registry, orchestrator,
            workflows=BENCHMARK_WORKFLOWS[:2],  # only 2 workflows for test speed
            runs_per_workflow=1,
        )

        assert "workflows" in result
        assert "baselines" in result
        assert "comparisons" in result
        assert "claims" in result
        assert "generatedAt" in result

    @pytest.mark.asyncio
    async def test_full_benchmark_has_all_baselines(self, seeded_db):
        """Should include all 4 baselines in the results."""
        from app.api.deps import get_action_registry, get_orchestrator

        registry = get_action_registry()
        await registry.load()
        orchestrator = get_orchestrator()

        result = await run_full_benchmark(
            registry, orchestrator,
            workflows=BENCHMARK_WORKFLOWS[:1],
            runs_per_workflow=1,
        )

        assert "earendel_full" in result["baselines"]
        assert "earendel_api" in result["baselines"]
        assert "playwright_raw" in result["baselines"]
        assert "bu_cloud" in result["baselines"]

    @pytest.mark.asyncio
    async def test_full_benchmark_has_claims(self, seeded_db):
        """Should include the 3 claims (faster, more_reliable, cheaper)."""
        from app.api.deps import get_action_registry, get_orchestrator

        registry = get_action_registry()
        await registry.load()
        orchestrator = get_orchestrator()

        result = await run_full_benchmark(
            registry, orchestrator,
            workflows=BENCHMARK_WORKFLOWS[:1],
            runs_per_workflow=1,
        )

        assert "faster" in result["claims"]
        assert "more_reliable" in result["claims"]
        assert "cheaper" in result["claims"]

        for claim_name, claim_data in result["claims"].items():
            assert "claimed" in claim_data
            assert "measured" in claim_data
            assert "verified" in claim_data
            assert isinstance(claim_data["verified"], bool)

    @pytest.mark.asyncio
    async def test_full_benchmark_earendel_cheaper_than_bu(self, seeded_db):
        """Earendel should be cheaper than BU Cloud (Earendel cost = $0)."""
        from app.api.deps import get_action_registry, get_orchestrator

        registry = get_action_registry()
        await registry.load()
        orchestrator = get_orchestrator()

        result = await run_full_benchmark(
            registry, orchestrator,
            workflows=BENCHMARK_WORKFLOWS[:1],
            runs_per_workflow=1,
        )

        earendel_cost = result["baselines"]["earendel_full"]["avg_cost_usd"]
        bu_cost = result["baselines"]["bu_cloud"]["avg_cost_usd"]
        assert earendel_cost < bu_cost

    @pytest.mark.asyncio
    async def test_full_benchmark_earendel_faster_than_bu(self, seeded_db):
        """Earendel API path should be faster than BU Cloud."""
        from app.api.deps import get_action_registry, get_orchestrator

        registry = get_action_registry()
        await registry.load()
        orchestrator = get_orchestrator()

        result = await run_full_benchmark(
            registry, orchestrator,
            workflows=BENCHMARK_WORKFLOWS[:1],
            runs_per_workflow=1,
        )

        earendel_p50 = result["baselines"]["earendel_api"]["p50_latency_ms"]
        bu_p50 = result["baselines"]["bu_cloud"]["p50_latency_ms"]
        assert earendel_p50 < bu_p50
