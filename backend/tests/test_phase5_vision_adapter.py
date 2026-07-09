"""Tests for Phase 5 — Real Vision Adapter (contract-aware VLM extraction).

Tests that:
1. _build_extraction_prompt generates a contract-aware prompt
2. _coerce_value coerces values to the right type
3. _get_screenshot_path finds the right screenshot from ctx
4. _extract_fields_via_vlm uses the contract-aware prompt (mocked VLM)
5. The adapter uses VLM-extracted fields (not _simulate_outputs) when VLM succeeds
6. The adapter falls back to simulation when VLM is unavailable
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

from app.adapters.base import ExecutionContext, AdapterResult
from app.adapters.vision_adapter import (
    VisionAdapter,
    _build_extraction_prompt,
    _VLM_ELEMENT_PROMPT,
)
from app.adapters.stealth import STEALTH_EVASION_COUNT
from app.core.domain.entities import (
    TypedAction, ActionContract, FieldSchema, TraceEvent,
)
from app.core.domain.value_objects import FieldSchema as FieldSchemaVO
from app.core.domain.enums import (
    AdapterType, Caller, RiskLevel, PermissionScope, WorkflowCategory, ActionStatus,
)
from app.infrastructure.telemetry import TraceCollector
from app.infrastructure.vault import CredentialVault


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

def _make_action(name: str = "downloadInvoice") -> TypedAction:
    return TypedAction(
        id=f"act_vision_test_{name}",
        connectorId="conn_test",
        name=name,
        signature=f"{name}(invoiceId: string)",
        description="Download an invoice from the supplier portal",
        category=WorkflowCategory.finance,
        contract=ActionContract(
            name=name,
            inputs=[FieldSchemaVO(name="invoiceId", type="string", required=True)],
            outputs=[
                FieldSchemaVO(name="invoiceNumber", type="string", required=True),
                FieldSchemaVO(name="pdfUrl", type="url", required=True),
                FieldSchemaVO(name="amount", type="number", required=True),
                FieldSchemaVO(name="status", type="string", required=True),
            ],
        ),
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.vision],
        preferredAdapter=AdapterType.vision,
        status=ActionStatus.testing,
    )


def _make_ctx(screenshots: list[str] | None = None) -> ExecutionContext:
    return ExecutionContext(
        caller=Caller.manual,
        risk_approved=True,
        run_id="run_vision_test",
        vault=CredentialVault(),
        telemetry=TraceCollector(),
        screenshots=screenshots or [],
    )


# --------------------------------------------------------------------------- #
# 1. _build_extraction_prompt                                                  #
# --------------------------------------------------------------------------- #

class TestBuildExtractionPrompt:
    """Tests for the contract-aware VLM prompt builder."""

    def test_prompt_includes_action_description(self):
        """The prompt should include the action's description."""
        action = _make_action()
        prompt, system = _build_extraction_prompt(action)
        assert "Download an invoice" in prompt

    def test_prompt_lists_all_output_fields(self):
        """The prompt should list all output fields from the contract."""
        action = _make_action()
        prompt, _ = _build_extraction_prompt(action)
        assert "invoiceNumber" in prompt
        assert "pdfUrl" in prompt
        assert "amount" in prompt
        assert "status" in prompt

    def test_prompt_includes_field_types(self):
        """The prompt should include the field types."""
        action = _make_action()
        prompt, _ = _build_extraction_prompt(action)
        assert "string" in prompt
        assert "url" in prompt
        assert "number" in prompt

    def test_prompt_asks_for_json(self):
        """The prompt should ask for a JSON response."""
        action = _make_action()
        prompt, _ = _build_extraction_prompt(action)
        assert "JSON" in prompt
        assert '"fields"' in prompt

    def test_system_prompt_is_extraction_focused(self):
        """The system prompt should focus on extraction, not element detection."""
        action = _make_action()
        _, system = _build_extraction_prompt(action)
        assert "extracting" in system.lower() or "extract" in system.lower()


# --------------------------------------------------------------------------- #
# 2. _coerce_value                                                             #
# --------------------------------------------------------------------------- #

class TestCoerceValue:
    """Tests for the value coercion method."""

    def test_coerce_string(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("INV-1001", "string") == "INV-1001"

    def test_coerce_number_plain(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("4280", "number") == 4280.0

    def test_coerce_number_with_currency(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("$4,280.50", "number") == 4280.50

    def test_coerce_number_with_euro(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("€1,200", "number") == 1200.0

    def test_coerce_number_invalid(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("not a number", "number") is None

    def test_coerce_boolean_true(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("true", "boolean") is True
        assert adapter._coerce_value("yes", "boolean") is True
        assert adapter._coerce_value("paid", "boolean") is True

    def test_coerce_boolean_false(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("false", "boolean") is False
        assert adapter._coerce_value("no", "boolean") is False

    def test_coerce_url_valid(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("https://example.com/invoice.pdf", "url") == "https://example.com/invoice.pdf"

    def test_coerce_url_invalid(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value("not a url", "url") is None

    def test_coerce_none(self):
        adapter = VisionAdapter()
        assert adapter._coerce_value(None, "string") is None


# --------------------------------------------------------------------------- #
# 3. _get_screenshot_path                                                      #
# --------------------------------------------------------------------------- #

class TestGetScreenshotPath:
    """Tests for the screenshot path resolution."""

    def test_returns_path_from_ctx(self):
        """Should return the most recent existing screenshot from ctx."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            path = f.name
        try:
            adapter = VisionAdapter()
            ctx = _make_ctx(screenshots=[path])
            assert adapter._get_screenshot_path(ctx) == path
        finally:
            os.unlink(path)

    def test_skips_nonexistent_paths(self):
        """Should skip paths that don't exist on disk."""
        adapter = VisionAdapter()
        ctx = _make_ctx(screenshots=["/tmp/nonexistent-1.png", "/tmp/nonexistent-2.png"])
        assert adapter._get_screenshot_path(ctx) == ""

    def test_falls_back_to_env_var(self):
        """Should fall back to EARENDEL_SCREENSHOT_PATH env var."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            path = f.name
        try:
            adapter = VisionAdapter()
            ctx = _make_ctx(screenshots=[])
            with patch.dict(os.environ, {"EARENDEL_SCREENSHOT_PATH": path}):
                assert adapter._get_screenshot_path(ctx) == path
        finally:
            os.unlink(path)

    def test_returns_empty_when_no_screenshots(self):
        """Should return empty string when no screenshots available."""
        adapter = VisionAdapter()
        ctx = _make_ctx(screenshots=[])
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EARENDEL_SCREENSHOT_PATH", None)
            assert adapter._get_screenshot_path(ctx) == ""

    def test_uses_most_recent_screenshot(self):
        """Should use the most recent (last) screenshot."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1:
            f1.write(b"fake PNG 1")
            path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2:
            f2.write(b"fake PNG 2")
            path2 = f2.name
        try:
            adapter = VisionAdapter()
            ctx = _make_ctx(screenshots=[path1, path2])
            # Should return the most recent (path2, last in the list)
            assert adapter._get_screenshot_path(ctx) == path2
        finally:
            os.unlink(path1)
            os.unlink(path2)


# --------------------------------------------------------------------------- #
# 4. _extract_fields_via_vlm (mocked VLM)                                      #
# --------------------------------------------------------------------------- #

class TestExtractFieldsViaVlm:
    """Tests for the contract-aware VLM extraction (with mocked VLM)."""

    @pytest.mark.asyncio
    async def test_extracts_fields_from_vlm_response(self):
        """Should extract and coerce fields from a VLM response."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            shot_path = f.name
        try:
            adapter = VisionAdapter()
            action = _make_action()
            ctx = _make_ctx(screenshots=[shot_path])

            # Mock the VLM to return extracted fields
            mock_vlm_result = {
                "fields": {
                    "invoiceNumber": "INV-1001",
                    "pdfUrl": "https://example.com/invoice.pdf",
                    "amount": "$4,280.50",
                    "status": "paid",
                }
            }
            with patch.object(adapter, "_call_vlm_raw", new_callable=AsyncMock, return_value=mock_vlm_result):
                result = await adapter._extract_fields_via_vlm(action, ctx)

            assert result is not None
            assert result["invoiceNumber"] == "INV-1001"
            assert result["pdfUrl"] == "https://example.com/invoice.pdf"
            assert result["amount"] == 4280.50  # coerced from "$4,280.50"
            assert result["status"] == "paid"
        finally:
            os.unlink(shot_path)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_screenshot(self):
        """Should return None when no screenshot is available."""
        adapter = VisionAdapter()
        action = _make_action()
        ctx = _make_ctx(screenshots=[])
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EARENDEL_SCREENSHOT_PATH", None)
            result = await adapter._extract_fields_via_vlm(action, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_vlm_fails(self):
        """Should return None when the VLM call fails."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            shot_path = f.name
        try:
            adapter = VisionAdapter()
            action = _make_action()
            ctx = _make_ctx(screenshots=[shot_path])

            with patch.object(adapter, "_call_vlm_raw", new_callable=AsyncMock, return_value=None):
                result = await adapter._extract_fields_via_vlm(action, ctx)
            assert result is None
        finally:
            os.unlink(shot_path)

    @pytest.mark.asyncio
    async def test_handles_null_fields(self):
        """Should handle null values from the VLM for fields not visible on page."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            shot_path = f.name
        try:
            adapter = VisionAdapter()
            action = _make_action()
            ctx = _make_ctx(screenshots=[shot_path])

            mock_vlm_result = {
                "fields": {
                    "invoiceNumber": "INV-1001",
                    "pdfUrl": None,
                    "amount": "$4,280.50",
                    "status": None,
                }
            }
            with patch.object(adapter, "_call_vlm_raw", new_callable=AsyncMock, return_value=mock_vlm_result):
                result = await adapter._extract_fields_via_vlm(action, ctx)

            assert result is not None
            assert result["invoiceNumber"] == "INV-1001"
            assert result["pdfUrl"] is None
            assert result["amount"] == 4280.50
            assert result["status"] is None
        finally:
            os.unlink(shot_path)


# --------------------------------------------------------------------------- #
# 5. Adapter execute() integration                                             #
# --------------------------------------------------------------------------- #

class TestVisionAdapterExecute:
    """Tests for the full execute() flow with VLM extraction."""

    @pytest.mark.asyncio
    async def test_uses_vlm_extracted_fields_when_available(self):
        """When VLM succeeds, the adapter should use VLM-extracted fields."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            shot_path = f.name
        try:
            adapter = VisionAdapter()
            action = _make_action()
            ctx = _make_ctx(screenshots=[shot_path])

            mock_vlm_result = {
                "fields": {
                    "invoiceNumber": "INV-1001",
                    "pdfUrl": "https://example.com/invoice.pdf",
                    "amount": "$4,280.50",
                    "status": "paid",
                }
            }
            with patch.object(adapter, "_call_vlm_raw", new_callable=AsyncMock, return_value=mock_vlm_result):
                result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

            assert result.success is True
            assert result.outputs["invoiceNumber"] == "INV-1001"
            assert result.outputs["pdfUrl"] == "https://example.com/invoice.pdf"
            assert result.outputs["amount"] == 4280.50
            assert result.outputs["status"] == "paid"

            # Should have a trace showing VLM extraction
            extract_traces = [t for t in result.traces if "extracted" in t.message.lower()]
            assert len(extract_traces) > 0
        finally:
            os.unlink(shot_path)

    @pytest.mark.asyncio
    async def test_falls_back_to_simulation_when_no_screenshot(self):
        """When no screenshot is available, should fall back to simulation."""
        adapter = VisionAdapter()
        action = _make_action()
        ctx = _make_ctx(screenshots=[])

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EARENDEL_SCREENSHOT_PATH", None)
            result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

        # Should fall back to simulation
        sim_traces = [t for t in result.traces if "simulat" in t.message.lower()]
        assert len(sim_traces) > 0

    @pytest.mark.asyncio
    async def test_backfills_missing_fields_from_simulation(self):
        """When VLM extracts some fields but not all, should backfill from sim."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            shot_path = f.name
        try:
            adapter = VisionAdapter()
            action = _make_action()
            ctx = _make_ctx(screenshots=[shot_path])

            # VLM extracts only 2 of 4 fields
            mock_vlm_result = {
                "fields": {
                    "invoiceNumber": "INV-1001",
                    "amount": "$4,280.50",
                    "pdfUrl": None,
                    "status": None,
                }
            }
            with patch.object(adapter, "_call_vlm_raw", new_callable=AsyncMock, return_value=mock_vlm_result):
                result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

            assert result.success is True
            # VLM-extracted fields should be present
            assert result.outputs["invoiceNumber"] == "INV-1001"
            assert result.outputs["amount"] == 4280.50
            # Backfilled fields should be present (from simulation)
            assert result.outputs.get("pdfUrl") is not None
            assert result.outputs.get("status") is not None

            # Should have a backfill trace
            backfill_traces = [t for t in result.traces if "backfill" in t.step]
            assert len(backfill_traces) > 0
        finally:
            os.unlink(shot_path)

    @pytest.mark.asyncio
    async def test_screenshot_handoff_trace_emitted(self):
        """Should emit a screenshot.handoff trace when screenshots are received."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG")
            shot_path = f.name
        try:
            adapter = VisionAdapter()
            action = _make_action()
            ctx = _make_ctx(screenshots=[shot_path])

            with patch.object(adapter, "_call_vlm_raw", new_callable=AsyncMock, return_value=None):
                result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

            handoff_traces = [t for t in result.traces if t.step == "screenshot.handoff"]
            assert len(handoff_traces) > 0
            assert "received" in handoff_traces[0].message.lower()
        finally:
            os.unlink(shot_path)
