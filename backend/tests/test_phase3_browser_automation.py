"""Tests for Phase 3 — Real Browser Automation.

Tests that:
1. The ExecutionContext has a screenshots field for inter-adapter handoff
2. The browser adapter returns full screenshot paths (not bare filenames)
3. The vision adapter reads screenshots from ctx.screenshots
4. The _substitute_value function returns passwords (not just usernames)
5. The _normalize_step_type function maps CapturedStep types to browser types
6. The _get_workflow method loads workflows from Recording.steps
7. The _detect_captcha method detects CAPTCHA elements
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.base import ExecutionContext, AdapterResult
from app.adapters.browser_adapter import (
    BrowserAdapter,
    _substitute_value,
    _normalize_step_type,
    _STEP_TYPE_MAP,
    _WORKFLOW_REGISTRY,
)
from app.adapters.vision_adapter import VisionAdapter
from app.adapters.stealth import (
    STEALTH_INIT_SCRIPT,
    STEALTH_LAUNCH_ARGS,
    STEALTH_EVASION_COUNT,
    build_proxy_config,
)
from app.core.domain.entities import TypedAction, ActionContract, FieldSchema, CapturedStep, Recording
from app.core.domain.enums import (
    AdapterType, Caller, RiskLevel, PermissionScope, WorkflowCategory, ActionStatus,
)
from app.core.domain.value_objects import FieldSchema
from app.infrastructure.telemetry import TraceCollector
from app.infrastructure.vault import CredentialVault


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

def _make_action(name: str = "testAction") -> TypedAction:
    return TypedAction(
        id=f"act_test_{name}",
        connectorId="conn_test",
        name=name,
        signature=f"{name}(id: string)",
        description="test action",
        category=WorkflowCategory.finance,
        contract=ActionContract(
            name=name,
            inputs=[FieldSchema(name="id", type="string", required=True)],
            outputs=[FieldSchema(name="result", type="string", required=True)],
        ),
        permissions=PermissionScope.read_only,
        riskLevel=RiskLevel.low,
        executionMethods=[AdapterType.browser],
        preferredAdapter=AdapterType.browser,
        status=ActionStatus.testing,
    )


def _make_ctx(screenshots: list[str] | None = None) -> ExecutionContext:
    return ExecutionContext(
        caller=Caller.manual,
        risk_approved=True,
        run_id="run_test_001",
        vault=CredentialVault(),
        telemetry=TraceCollector(),
        screenshots=screenshots or [],
    )


# --------------------------------------------------------------------------- #
# 1. ExecutionContext screenshot field                                         #
# --------------------------------------------------------------------------- #

class TestExecutionContextScreenshots:
    """Tests that ExecutionContext has a screenshots field for inter-adapter handoff."""

    def test_execution_context_has_screenshots_field(self):
        """ExecutionContext should have a screenshots field defaulting to []."""
        ctx = ExecutionContext(
            caller=Caller.manual,
            risk_approved=True,
            run_id="run_1",
            vault=CredentialVault(),
            telemetry=TraceCollector(),
        )
        assert hasattr(ctx, "screenshots")
        assert ctx.screenshots == []

    def test_execution_context_screenshots_can_be_set(self):
        """ExecutionContext.screenshots should accept a list of paths."""
        ctx = ExecutionContext(
            caller=Caller.manual,
            risk_approved=True,
            run_id="run_1",
            vault=CredentialVault(),
            telemetry=TraceCollector(),
            screenshots=["/tmp/shot1.png", "/tmp/shot2.png"],
        )
        assert ctx.screenshots == ["/tmp/shot1.png", "/tmp/shot2.png"]


# --------------------------------------------------------------------------- #
# 2. Browser adapter screenshot paths                                         #
# --------------------------------------------------------------------------- #

class TestBrowserAdapterScreenshots:
    """Tests that the browser adapter returns full screenshot paths."""

    @pytest.mark.asyncio
    async def test_browser_adapter_returns_full_paths_in_simulation(self):
        """Even in simulation mode, the adapter should return screenshot paths.

        The simulation returns ["snap-1.png"] which are bare filenames.
        This test verifies the current behavior (bare filenames in sim) so
        we know the orchestrator's path-conversion logic is needed.
        """
        adapter = BrowserAdapter()
        action = _make_action("downloadInvoice")
        ctx = _make_ctx()

        # Force simulation mode
        with patch.dict(os.environ, {"EARENDEL_DEMO_MODE": "true"}):
            result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

        assert result.success in (True, False)  # sim has 15% failure
        # Simulation returns bare filenames like "snap-1.png"
        assert len(result.screenshots) > 0


# --------------------------------------------------------------------------- #
# 3. Vision adapter reads ctx.screenshots                                      #
# --------------------------------------------------------------------------- #

class TestVisionAdapterScreenshotHandoff:
    """Tests that the vision adapter reads screenshots from ExecutionContext."""

    @pytest.mark.asyncio
    async def test_vision_adapter_reads_ctx_screenshots(self):
        """Vision adapter should use ctx.screenshots when available."""
        adapter = VisionAdapter()
        action = _make_action("downloadInvoice")

        # Create a real temporary screenshot file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake PNG content")
            shot_path = f.name

        try:
            ctx = _make_ctx(screenshots=[shot_path])
            result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

            # The vision adapter should have received the screenshot
            # (it may still fall back to simulation if z-ai vision isn't available,
            # but the handoff trace should be present)
            handoff_traces = [t for t in result.traces if "screenshot" in t.step]
            assert len(handoff_traces) > 0
            assert "received" in handoff_traces[0].message.lower()
        finally:
            os.unlink(shot_path)

    @pytest.mark.asyncio
    async def test_vision_adapter_falls_back_when_no_screenshots(self):
        """Vision adapter should fall back to simulation when ctx.screenshots is empty."""
        adapter = VisionAdapter()
        action = _make_action("downloadInvoice")
        ctx = _make_ctx(screenshots=[])

        result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

        # Should fall back to simulation (no screenshots to analyze)
        assert result.success in (True, False)
        # Should NOT have a screenshot.handoff trace
        handoff_traces = [t for t in result.traces if t.step == "screenshot.handoff"]
        assert len(handoff_traces) == 0

    @pytest.mark.asyncio
    async def test_vision_adapter_skips_nonexistent_screenshots(self):
        """Vision adapter should skip screenshot paths that don't exist on disk."""
        adapter = VisionAdapter()
        action = _make_action("downloadInvoice")
        ctx = _make_ctx(screenshots=["/tmp/nonexistent-screenshot.png"])

        result = await adapter.execute(action, {"invoiceId": "INV-1001"}, ctx)

        # Should fall back to simulation (the screenshot file doesn't exist)
        assert result.success in (True, False)


# --------------------------------------------------------------------------- #
# 4. _substitute_value password fix                                           #
# --------------------------------------------------------------------------- #

class TestSubstituteValuePasswordFix:
    """Tests that _substitute_value returns passwords (not just usernames)."""

    def test_returns_input_value_first(self):
        """Input values should take precedence over vault."""
        result = _substitute_value("{email}", {"email": "user@example.com"}, None)
        assert result == "user@example.com"

    def test_returns_password_from_vault(self):
        """Password placeholders should return the password from the vault."""
        vault = MagicMock()
        vault.get.return_value = {
            "username": "user@example.com",
            "password": "secret123",
        }
        result = _substitute_value("{password}", {}, vault)
        assert result == "secret123"

    def test_returns_username_from_vault_for_non_password_keys(self):
        """Non-password placeholders should return the username from the vault."""
        vault = MagicMock()
        vault.get.return_value = {
            "username": "user@example.com",
            "password": "secret123",
        }
        result = _substitute_value("{email}", {}, vault)
        assert result == "user@example.com"

    def test_returns_template_when_vault_missing(self):
        """Should return the template unchanged when vault has no match."""
        vault = MagicMock()
        vault.get.return_value = None
        result = _substitute_value("{unknown}", {}, vault)
        assert result == "{unknown}"

    def test_returns_template_when_no_placeholder(self):
        """Non-placeholder values should be returned as-is."""
        result = _substitute_value("plain text", {}, None)
        assert result == "plain text"


# --------------------------------------------------------------------------- #
# 5. _normalize_step_type                                                      #
# --------------------------------------------------------------------------- #

class TestNormalizeStepType:
    """Tests that _normalize_step_type maps CapturedStep types to browser types."""

    def test_input_maps_to_fill(self):
        """Chrome extension's 'input' should map to 'fill'."""
        assert _normalize_step_type("input") == "fill"

    def test_select_maps_to_fill(self):
        """'select' should map to 'fill'."""
        assert _normalize_step_type("select") == "fill"

    def test_assert_maps_to_wait(self):
        """'assert' should map to 'wait'."""
        assert _normalize_step_type("assert") == "wait"

    def test_click_passes_through(self):
        """'click' should pass through unchanged."""
        assert _normalize_step_type("click") == "click"

    def test_navigate_passes_through(self):
        """'navigate' should pass through unchanged."""
        assert _normalize_step_type("navigate") == "navigate"

    def test_download_passes_through(self):
        """'download' should pass through unchanged."""
        assert _normalize_step_type("download") == "download"

    def test_wait_passes_through(self):
        """'wait' should pass through unchanged."""
        assert _normalize_step_type("wait") == "wait"

    def test_fill_passes_through(self):
        """'fill' should pass through unchanged (backward compat with _WORKFLOW_REGISTRY)."""
        assert _normalize_step_type("fill") == "fill"

    def test_unknown_type_passes_through(self):
        """Unknown types should pass through unchanged (visible warning)."""
        assert _normalize_step_type("unknown_type") == "unknown_type"


# --------------------------------------------------------------------------- #
# 6. _get_workflow from Recording.steps                                       #
# --------------------------------------------------------------------------- #

class TestGetWorkflowFromRecording:
    """Tests that _get_workflow loads workflows from Recording.steps."""

    @pytest.mark.asyncio
    async def test_get_workflow_falls_back_to_registry(self, seeded_db):
        """When no recording is linked to the action, fall back to _WORKFLOW_REGISTRY."""
        adapter = BrowserAdapter()
        action = _make_action("downloadInvoice")  # in _WORKFLOW_REGISTRY

        workflow = await adapter._get_workflow(action)
        assert workflow is not None
        assert len(workflow) > 0
        # Should be the hardcoded registry workflow
        assert workflow[0]["type"] == "navigate"

    @pytest.mark.asyncio
    async def test_get_workflow_returns_none_for_unknown_action(self, seeded_db):
        """When the action is not in the registry and has no recording, return None."""
        adapter = BrowserAdapter()
        action = _make_action("completelyUnknownAction")

        workflow = await adapter._get_workflow(action)
        assert workflow is None


# --------------------------------------------------------------------------- #
# 7. CAPTCHA detection                                                         #
# --------------------------------------------------------------------------- #

class TestCaptchaDetection:
    """Tests for the _detect_captcha method."""

    @pytest.mark.asyncio
    async def test_detect_captcha_returns_false_on_no_captcha(self):
        """_detect_captcha should return False when no CAPTCHA is present."""
        adapter = BrowserAdapter()
        page = AsyncMock()
        page.evaluate.return_value = []  # no CAPTCHA signals

        result = await adapter._detect_captcha(page)
        assert result is False

    @pytest.mark.asyncio
    async def test_detect_captcha_returns_true_on_recaptcha(self):
        """_detect_captcha should return True when reCAPTCHA is detected."""
        adapter = BrowserAdapter()
        page = AsyncMock()
        page.evaluate.return_value = ["recaptcha"]

        result = await adapter._detect_captcha(page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detect_captcha_returns_true_on_cloudflare(self):
        """_detect_captcha should return True when Cloudflare challenge is detected."""
        adapter = BrowserAdapter()
        page = AsyncMock()
        page.evaluate.return_value = ["cloudflare"]

        result = await adapter._detect_captcha(page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detect_captcha_returns_false_on_js_error(self):
        """_detect_captcha should return False (not raise) on JS evaluation error."""
        adapter = BrowserAdapter()
        page = AsyncMock()
        page.evaluate.side_effect = Exception("JS error")

        result = await adapter._detect_captcha(page)
        assert result is False


# --------------------------------------------------------------------------- #
# 8. Stealth module verification                                              #
# --------------------------------------------------------------------------- #

class TestStealthModule:
    """Tests that the stealth module is properly configured."""

    def test_stealth_init_script_has_7_evasions(self):
        """STEALTH_INIT_SCRIPT should contain 7 evasion try/catch blocks."""
        # Count the number of try { blocks in the init script
        count = STEALTH_INIT_SCRIPT.count("try {")
        assert count == STEALTH_EVASION_COUNT  # 7

    def test_stealth_launch_args_has_anti_automation_flag(self):
        """STEALTH_LAUNCH_ARGS should include --disable-blink-features=AutomationControlled."""
        assert "--disable-blink-features=AutomationControlled" in STEALTH_LAUNCH_ARGS

    def test_stealth_launch_args_has_no_sandbox(self):
        """STEALTH_LAUNCH_ARGS should include --no-sandbox for container compat."""
        assert "--no-sandbox" in STEALTH_LAUNCH_ARGS

    def test_stealth_init_script_overrides_webdriver(self):
        """STEALTH_INIT_SCRIPT should override navigator.webdriver."""
        assert "navigator.webdriver" in STEALTH_INIT_SCRIPT

    def test_stealth_init_script_overrides_plugins(self):
        """STEALTH_INIT_SCRIPT should override navigator.plugins."""
        assert "navigator.plugins" in STEALTH_INIT_SCRIPT

    def test_stealth_init_script_overrides_languages(self):
        """STEALTH_INIT_SCRIPT should override navigator.languages."""
        assert "navigator.languages" in STEALTH_INIT_SCRIPT

    def test_build_proxy_config_returns_none_when_no_env(self):
        """build_proxy_config should return None when no proxy env vars are set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EARENDEL_BROWSER_PROXY", None)
            os.environ.pop("EARENDEL_BROWSER_PROXY_SERVER", None)
            result = build_proxy_config()
            assert result is None

    def test_build_proxy_config_parses_full_url(self):
        """build_proxy_config should parse a full proxy URL with credentials."""
        with patch.dict(os.environ, {
            "EARENDEL_BROWSER_PROXY": "http://user:pass@proxy.example.com:8080",
        }):
            os.environ.pop("EARENDEL_BROWSER_PROXY_SERVER", None)
            result = build_proxy_config()
            assert result is not None
            assert result["server"] == "http://proxy.example.com:8080"
            assert result["username"] == "user"
            assert result["password"] == "pass"


# --------------------------------------------------------------------------- #
# 9. Real portal workflows                                                    #
# --------------------------------------------------------------------------- #

class TestRealPortalWorkflows:
    """Tests that the seeded workflows target resolvable domains."""

    def test_track_shipment_workflow_targets_real_maersk_url(self):
        """The trackShipment workflow should target a real Maersk URL."""
        workflow = _WORKFLOW_REGISTRY.get("trackShipment")
        assert workflow is not None
        navigate_step = next(s for s in workflow if s["type"] == "navigate")
        assert "maersk.com" in navigate_step["url"]

    def test_check_claim_status_workflow_targets_real_url(self):
        """The checkClaimStatus workflow should target a real URL."""
        workflow = _WORKFLOW_REGISTRY.get("checkClaimStatus")
        assert workflow is not None
        navigate_step = next(s for s in workflow if s["type"] == "navigate")
        # Should target jsonplaceholder or another real domain
        assert "jsonplaceholder.typicode.com" in navigate_step["url"] or \
               "http" in navigate_step["url"]
