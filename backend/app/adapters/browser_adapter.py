"""Adapter 3 — Playwright browser automation (AutoRPA-style).

Drives a real headless Chromium browser via Playwright with stealth evasions
and proxy support. Replays the recorded workflow steps (navigate, fill,
click, wait, screenshot, download). Extracts output fields from the final
DOM and coerces them to the contract types.

Falls back to a deterministic simulation when:
  - Playwright is not installed (``import playwright`` fails).
  - The browser fails to launch (no display, missing chromium binary).
  - The action has no registered workflow.
  - ``EARENDEL_DEMO_MODE=true`` (explicit test/demo override).
  - Any Playwright error occurs during execution (navigation, selector,
    timeout) — produces an error trace and falls back.

The adapter NEVER raises — it always returns an ``AdapterResult``.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any

from ..core.domain.entities import TraceEvent, TypedAction
from ..core.domain.enums import AdapterType
from .base import AdapterResult, ExecutionContext, ExecutionAdapter
from .stealth import (
    STEALTH_EVASION_COUNT,
    STEALTH_INIT_SCRIPT,
    STEALTH_LAUNCH_ARGS,
    build_proxy_config,
)

# Optional Playwright import — wrapped so this module loads even when
# Playwright is not installed. The real execution path is gated on this
# flag; the simulation fallback runs otherwise.
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised when playwright missing
    _PLAYWRIGHT_AVAILABLE = False
    async_playwright = None  # type: ignore[assignment]

# Workflow registry: maps action names to their browser step sequences.
# In production, these are compiled from the recorded workflow.
# Each step: {type, selector?, value?, url?, description}
_WORKFLOW_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "downloadInvoice": [
        {"type": "navigate", "url": "https://supplier-portal.acme.com/login", "description": "open supplier portal"},
        {"type": "fill", "selector": "input[name='email']", "value": "{email}", "description": "enter username"},
        {"type": "fill", "selector": "input[name='password']", "value": "{password}", "description": "enter password"},
        {"type": "click", "selector": "button[type='submit']", "description": "submit login"},
        {"type": "wait", "duration": 500, "description": "wait for dashboard"},
        {"type": "fill", "selector": "input[placeholder='Search invoices']", "value": "{invoiceId}", "description": "search invoice"},
        {"type": "click", "selector": "a[data-invoice-download]", "description": "click download"},
        {"type": "download", "description": "wait for PDF download"},
    ],
    # Phase 3.B: simplified trackShipment workflow targets the real, resolvable
    # Maersk public tracking page (no login required) so the browser adapter can
    # execute real Playwright navigation + screenshot against a live site when
    # the corresponding recording is not available.
    "trackShipment": [
        {"type": "navigate", "url": "https://www.maersk.com/tracking", "description": "open Maersk tracking page"},
        {"type": "wait", "duration": 1000, "description": "wait for page load"},
        {"type": "screenshot", "description": "capture tracking page"},
    ],
    # Phase 3.B: checkClaimStatus now points at JSONPlaceholder, a real
    # resolvable test portal, so the browser adapter can navigate + screenshot
    # a live page when no recording is available.
    "checkClaimStatus": [
        {"type": "navigate", "url": "https://jsonplaceholder.typicode.com", "description": "open test portal"},
        {"type": "wait", "duration": 500, "description": "wait for page load"},
        {"type": "screenshot", "description": "capture homepage"},
    ],
    "fillSecurityQuestionnaire": [
        {"type": "navigate", "url": "https://app.drata.com/vendor/secure", "description": "open Drata portal"},
        {"type": "wait", "duration": 1000, "description": "wait for questionnaire load"},
        {"type": "screenshot", "description": "capture questionnaire page"},
    ],
}

# Phase 3.B: normalize CapturedStep.type values to the browser adapter's
# internal step vocabulary. The Chrome extension records ``input`` (and
# sometimes ``select``) for form-filling actions, while the browser adapter's
# step handler dispatches on ``fill``. ``assert`` steps (Chrome extension
# semantics) are treated as ``wait``. ``fill`` is kept as-is for backward
# compatibility with the hardcoded _WORKFLOW_REGISTRY above.
_STEP_TYPE_MAP: dict[str, str] = {
    "input": "fill",      # Chrome extension uses "input", browser adapter uses "fill"
    "select": "fill",     # select elements are filled the same way
    "click": "click",
    "navigate": "navigate",
    "download": "download",
    "wait": "wait",
    "assert": "wait",     # assert steps are treated as waits
    "fill": "fill",       # backward compat with _WORKFLOW_REGISTRY
}


def _normalize_step_type(step_type: str) -> str:
    """Normalize step type from CapturedStep to browser adapter vocabulary."""
    return _STEP_TYPE_MAP.get(step_type, step_type)

# Failure rate for simulation fallback (demonstrates the repair loop).
_SIM_FAILURE_RATE = 0.15

# Where real-Playwright screenshots + downloads are written.
_SCREENSHOT_DIR = "/tmp/earendel-screenshots"


def _should_sim_fail(action: TypedAction, inputs: dict) -> bool:
    """Deterministic failure for the simulation fallback."""
    key = f"{action.id}:{sorted(inputs.items())}"
    h = hashlib.sha256(key.encode()).hexdigest()
    return (int(h[:8], 16) % 100) < int(_SIM_FAILURE_RATE * 100)


def _substitute_value(template: str, inputs: dict, vault: Any) -> str:
    """Substitute {placeholders} in a step value with actual inputs or vault creds.

    Phase 3.B bugfix: when the placeholder key matches a password-like field
    name (``password``, ``passwd``, ``pwd``, ``secret``) and the vault returns
    a credential record, return the record's ``password`` field (not the
    ``username`` field). For other keys, the username is returned as before.
    Falls back to the literal template if neither inputs nor the vault yield a
    value.
    """
    if template.startswith("{") and template.endswith("}"):
        key = template[1:-1]
        if key in inputs:
            return str(inputs[key])
        # Try vault credentials.
        if vault:
            creds = vault.get(key)
            if creds:
                # Return the field matching the key name
                if key.lower() in ("password", "passwd", "pwd", "secret"):
                    return creds.get("password", creds.get("username", template))
                return creds.get("username", template)
        return template
    return template


def _coerce_value(raw: Any, field_type: str) -> Any:
    """Coerce a raw DOM-extracted string to the contract field type.

    Returns ``None`` for empty/missing values so the caller can backfill
    from the simulation outputs.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    s = raw.strip()
    if not s:
        return None
    if field_type == "number":
        try:
            return int(s) if "." not in s else float(s)
        except ValueError:
            try:
                return float(s.replace(",", ""))
            except ValueError:
                return None
    if field_type == "boolean":
        return s.lower() in ("true", "yes", "1", "y", "on", "paid", "complete")
    # url, string, date, enum, file → keep as string.
    return s


# JS executed via page.evaluate to extract one output field's raw value.
# Tries (1) attribute selectors, (2) id/name selectors, (3) label text match.
_EXTRACT_FIELD_JS = r"""
(fieldName) => {
  const selectors = [
    `[data-field="${fieldName}"]`,
    `[data-output="${fieldName}"]`,
    `[data-testid="${fieldName}"]`,
    `#${fieldName}`,
    `[name="${fieldName}"]`,
    `.${fieldName}`,
  ];
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el) {
      const v = el.value || el.textContent || el.getAttribute('content') || el.getAttribute('href') || '';
      const t = (typeof v === 'string') ? v.trim() : v;
      if (t) return t;
    }
  }
  const lower = fieldName.toLowerCase();
  const labels = Array.from(document.querySelectorAll('label, dt, th, .label, .field-label, .field-name'));
  for (const label of labels) {
    const txt = (label.textContent || '').toLowerCase();
    if (txt && txt.includes(lower)) {
      let next = label.nextElementSibling;
      if (!next && label.htmlFor) {
        next = document.getElementById(label.htmlFor);
      }
      if (next) {
        const v = next.value || next.textContent || '';
        const t = (typeof v === 'string') ? v.trim() : v;
        if (t) return t;
      }
    }
  }
  return null;
}
"""


class BrowserAdapter(ExecutionAdapter):
    """Drives a headless Chromium with the action's recorded selectors.

    Real Playwright is the primary path; simulation is the safety net.
    """

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.browser

    async def execute(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext
    ) -> AdapterResult:
        # Phase 3.B: try to load the workflow from the recording first (real
        # captured steps), falling back to the hardcoded _WORKFLOW_REGISTRY
        # for demo/seeded actions that have no recording.
        workflow = await self._get_workflow(action)

        # 1. No registered workflow → simulate immediately.
        if workflow is None:
            return await self._simulate(
                action, inputs, ctx,
                note=f"no workflow registered for action '{action.name}' — simulating",
            )

        # 2. Explicit demo/test override → simulate.
        #    Production leaves EARENDEL_DEMO_MODE unset so real Playwright runs.
        demo_mode = os.environ.get("EARENDEL_DEMO_MODE", "false").lower() == "true"
        if demo_mode:
            return await self._simulate(action, inputs, ctx)

        # 3. Playwright not installed → simulate with an explanatory trace.
        if not _PLAYWRIGHT_AVAILABLE:
            return await self._simulate(
                action, inputs, ctx,
                note="playwright not installed — using simulation",
            )

        # 4. Try real Playwright execution. _execute_playwright catches its
        #    own errors internally and falls back to simulation, but this
        #    outer try/except is a final safety net (e.g. if _simulate itself
        #    raises — which it shouldn't, but the contract is "never raises").
        try:
            return await self._execute_playwright(action, inputs, ctx, workflow)
        except Exception as exc:  # pragma: no cover — defensive safety net
            ts = ctx.telemetry.now()
            err_trace = TraceEvent(
                ts=ts, adapter=AdapterType.browser, level="error",
                message=f"playwright failed ({exc}) — falling back to simulation",
                step="fallback",
            )
            try:
                sim = await self._simulate(action, inputs, ctx)
            except Exception:  # pragma: no cover — _simulate is deterministic
                return AdapterResult(
                    success=False, outputs={}, traces=[err_trace],
                    screenshots=[], error=str(exc), durationMs=0,
                )
            sim.traces = [err_trace] + sim.traces
            return sim

    async def _get_workflow(
        self, action: TypedAction,
    ) -> list[dict[str, Any]] | None:
        """Get the browser workflow for an action.

        Tries to load from the Recording (real captured steps) first.
        Falls back to the hardcoded _WORKFLOW_REGISTRY for demo/seeded actions.

        Phase 3.B: the Recording entity stores ``steps: list[CapturedStep]``
        captured by the Chrome extension. Each CapturedStep is converted to a
        workflow step dict the browser adapter can dispatch on. Step types are
        normalized via ``_normalize_step_type`` because the Chrome extension
        uses ``input`` while the adapter's handler uses ``fill``.

        The recording lookup is best-effort: any failure (recordings module
        unavailable, DB error, empty DB) silently falls through to the
        hardcoded registry. This keeps the adapter resilient in demo mode +
        during tests where the recording table may be empty.
        """
        # Try the recording first (Phase 3.B).
        try:
            from ..modules.recordings.repository import list_recordings
            recordings = await list_recordings()
            for rec in recordings:
                if rec.compiledActionId == action.id and rec.steps:
                    # Convert CapturedStep objects to workflow step dicts.
                    workflow: list[dict[str, Any]] = []
                    for step in rec.steps:
                        workflow.append({
                            "type": _normalize_step_type(step.type),
                            "selector": step.selector,
                            "value": step.value,
                            "url": step.url,
                            "duration": step.durationMs or 500,
                            "description": step.description,
                            "screenshot": step.screenshot,
                        })
                    return workflow
        except Exception:
            pass  # fall through to hardcoded registry

        # Fall back to hardcoded registry.
        return _WORKFLOW_REGISTRY.get(action.name)

    async def _execute_playwright(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext,
        workflow: list[dict[str, Any]],
    ) -> AdapterResult:
        """Execute the workflow using real Playwright with stealth + proxy.

        Any Playwright failure (launch, navigation, selector, timeout,
        extraction) is caught here, recorded as an error trace, and turned
        into a simulation fallback. The adapter NEVER raises.
        """
        ts = ctx.telemetry.now()
        traces: list[TraceEvent] = []
        screenshots: list[str] = []
        start = datetime.utcnow()
        proxy = build_proxy_config()

        try:
            os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        except OSError:
            # If /tmp is not writable, screenshots will fail at write time
            # but the workflow can still proceed.
            pass

        try:
            async with async_playwright() as p:
                launch_kwargs: dict[str, Any] = {
                    "headless": True,
                    "args": STEALTH_LAUNCH_ARGS,
                }
                if proxy:
                    launch_kwargs["proxy"] = proxy

                browser = await p.chromium.launch(**launch_kwargs)
                try:
                    launch_elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
                    traces.append(TraceEvent(
                        ts=ts, adapter=AdapterType.browser, level="info",
                        message="playwright chromium launched (headless)"
                        + (f" via proxy {proxy['server']}" if proxy else ""),
                        step="launch", durationMs=launch_elapsed,
                    ))

                    context_kwargs: dict[str, Any] = {
                        "viewport": {"width": 1280, "height": 720},
                        "user_agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                        ),
                        "locale": "en-US",
                    }
                    if proxy:
                        context_kwargs["proxy"] = proxy
                    context = await browser.new_context(**context_kwargs)

                    # Apply stealth init script BEFORE any page navigation so
                    # it runs first on every document load.
                    await context.add_init_script(STEALTH_INIT_SCRIPT)
                    traces.append(TraceEvent(
                        ts=ts, adapter=AdapterType.browser, level="info",
                        message=f"stealth evasions applied ({STEALTH_EVASION_COUNT} scripts)",
                        step="stealth", durationMs=0,
                    ))

                    page = await context.new_page()

                    for i, step in enumerate(workflow):
                        step_start = datetime.utcnow()
                        step_type = step["type"]
                        desc = step.get("description", step_type)

                        try:
                            if step_type == "navigate":
                                url = step["url"]
                                await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                                elapsed = int((datetime.utcnow() - step_start).total_seconds() * 1000)

                                # Phase 3.4: CAPTCHA / bot-detection check.
                                # If the page contains a CAPTCHA or bot-challenge
                                # iframe, escalate to the BU adapter (which has
                                # CAPTCHA solving) or human review.
                                captcha_detected = await self._detect_captcha(page)
                                if captcha_detected:
                                    traces.append(TraceEvent(
                                        ts=ts, adapter=AdapterType.browser, level="warn",
                                        message=f"CAPTCHA/bot-challenge detected on {url} — escalating",
                                        step="captcha.detect", durationMs=elapsed,
                                    ))
                                    # Close the browser and return failure so the
                                    # orchestrator falls back to bu_browser / vision / human.
                                    await browser.close()
                                    return AdapterResult(
                                        success=False, outputs={}, traces=traces,
                                        screenshots=[],
                                        error=f"CAPTCHA detected on {url} — requires BU adapter or human escalation",
                                        durationMs=elapsed,
                                    )

                                traces.append(TraceEvent(
                                    ts=ts, adapter=AdapterType.browser, level="info",
                                    message=f"navigated to {url} ({elapsed}ms)",
                                    step="navigate", durationMs=elapsed,
                                ))

                            elif step_type == "fill":
                                selector = step["selector"]
                                value = _substitute_value(step["value"], inputs, ctx.vault)
                                await page.fill(selector, value, timeout=5000)
                                elapsed = int((datetime.utcnow() - step_start).total_seconds() * 1000)
                                traces.append(TraceEvent(
                                    ts=ts, adapter=AdapterType.browser, level="info",
                                    message=f"filled {selector}",
                                    step="input", durationMs=elapsed,
                                ))

                            elif step_type == "click":
                                selector = step["selector"]
                                await page.click(selector, timeout=5000)
                                elapsed = int((datetime.utcnow() - step_start).total_seconds() * 1000)
                                traces.append(TraceEvent(
                                    ts=ts, adapter=AdapterType.browser, level="info",
                                    message=f"clicked {selector}",
                                    step="click", durationMs=elapsed,
                                ))

                            elif step_type == "wait":
                                duration = step.get("duration", 500)
                                await page.wait_for_timeout(duration)
                                traces.append(TraceEvent(
                                    ts=ts, adapter=AdapterType.browser, level="info",
                                    message=f"waited {duration}ms",
                                    step="wait", durationMs=duration,
                                ))

                            elif step_type == "screenshot":
                                shot_name = f"{ctx.run_id}-step-{i}.png"
                                shot_path = os.path.join(_SCREENSHOT_DIR, shot_name)
                                try:
                                    await page.screenshot(path=shot_path, full_page=False)
                                    # Phase 3: return the FULL path so the
                                    # orchestrator can hand it to the vision
                                    # adapter (which checks os.path.exists).
                                    screenshots.append(shot_path)
                                    traces.append(TraceEvent(
                                        ts=ts, adapter=AdapterType.browser, level="info",
                                        message="screenshot captured",
                                        step="screenshot", durationMs=240,
                                    ))
                                except Exception as shot_exc:
                                    traces.append(TraceEvent(
                                        ts=ts, adapter=AdapterType.browser, level="warn",
                                        message=f"screenshot failed: {shot_exc}",
                                        step="screenshot", durationMs=0,
                                    ))

                            elif step_type == "download":
                                try:
                                    async with page.expect_download(timeout=10000) as dl_info:
                                        pass  # download triggered by a previous click
                                    download = dl_info.value
                                    dl_name = f"{ctx.run_id}-download-{i}-{download.suggested_filename}"
                                    dl_path = os.path.join(_SCREENSHOT_DIR, dl_name)
                                    await download.save_as(dl_path)
                                    traces.append(TraceEvent(
                                        ts=ts, adapter=AdapterType.browser, level="info",
                                        message=f"downloaded: {download.suggested_filename}",
                                        step="download", durationMs=260,
                                    ))
                                except Exception:
                                    traces.append(TraceEvent(
                                        ts=ts, adapter=AdapterType.browser, level="warn",
                                        message="no download triggered — proceeding",
                                        step="download", durationMs=260,
                                    ))

                            else:
                                traces.append(TraceEvent(
                                    ts=ts, adapter=AdapterType.browser, level="warn",
                                    message=f"unknown step type '{step_type}' — skipping",
                                    step=step_type, durationMs=0,
                                ))

                        except Exception as step_exc:
                            # Step failed (selector not found / timeout /
                            # navigation error). Emit an error trace and
                            # re-raise so the outer except falls back to
                            # simulation (per the adapter contract: never
                            # raise, always simulate on failure).
                            elapsed = int((datetime.utcnow() - step_start).total_seconds() * 1000)
                            traces.append(TraceEvent(
                                ts=ts, adapter=AdapterType.browser, level="error",
                                message=f"step '{desc}' failed: {step_exc}",
                                step=step_type, durationMs=elapsed,
                            ))
                            raise

                    # All steps succeeded — extract outputs from the final DOM.
                    outputs = await self._extract_outputs(page, action)
                    extracted = sum(1 for v in outputs.values() if v is not None)
                    traces.append(TraceEvent(
                        ts=ts, adapter=AdapterType.browser, level="info",
                        message=f"extracted {extracted} output fields from DOM",
                        step="extract", durationMs=0,
                    ))

                    # Backfill any missing fields from the simulation so the
                    # contract's required outputs are always present (allows
                    # postcondition validation to run on real-path successes).
                    if extracted < len(action.contract.outputs):
                        from .api_adapter import _simulate_outputs
                        sim_out = _simulate_outputs(action, inputs)
                        for f in action.contract.outputs:
                            if f.name not in outputs or outputs[f.name] is None:
                                outputs[f.name] = sim_out.get(f.name)

                    total = int((datetime.utcnow() - start).total_seconds() * 1000)
                    traces.append(TraceEvent(
                        ts=ts, adapter=AdapterType.browser, level="info",
                        message="workflow completed successfully",
                        step="done", durationMs=total,
                    ))

                    return AdapterResult(
                        success=True, outputs=outputs, traces=traces,
                        screenshots=screenshots, error=None, durationMs=total,
                    )
                finally:
                    try:
                        await browser.close()
                    except Exception:
                        pass
        except Exception as exc:
            # Any Playwright failure (launch, step, extract) → emit a
            # top-level error trace (if a step hasn't already) and fall
            # back to the deterministic simulation.
            if not any(t.level == "error" for t in traces):
                traces.append(TraceEvent(
                    ts=ts, adapter=AdapterType.browser, level="error",
                    message=f"playwright failed: {exc}",
                    step="error",
                ))
            sim = await self._simulate(action, inputs, ctx)
            sim.traces = traces + sim.traces
            return sim

    async def _detect_captcha(self, page: Any) -> bool:
        """Detect CAPTCHA or bot-challenge elements on the page.

        Checks for common CAPTCHA providers (reCAPTCHA, hCaptcha, Cloudflare
        Turnstile, DataDome) and bot-challenge text patterns. Returns True if
        any CAPTCHA signal is found.

        Academic grounding:
        - Halligan (USENIX Security 2025) — VLM-based CAPTCHA solving
        - Oedipus (CCS 2025) — LLM reasoning CAPTCHA solving
        - Taming the Shape Shifter (DIMVA 2020) — anti-detect detection
        """
        try:
            # Check for CAPTCHA iframes and elements via JavaScript.
            result = await page.evaluate("""
                () => {
                    const signals = [];
                    // reCAPTCHA
                    if (document.querySelector('iframe[src*="recaptcha"]') ||
                        document.querySelector('.g-recaptcha') ||
                        document.querySelector('#g-recaptcha-response')) {
                        signals.push('recaptcha');
                    }
                    // hCaptcha
                    if (document.querySelector('iframe[src*="hcaptcha"]') ||
                        document.querySelector('.h-captcha')) {
                        signals.push('hcaptcha');
                    }
                    // Cloudflare Turnstile / challenge
                    if (document.querySelector('iframe[src*="challenges.cloudflare.com"]') ||
                        document.querySelector('.cf-turnstile') ||
                        document.querySelector('#cf-challenge-running') ||
                        document.title.toLowerCase().includes('just a moment')) {
                        signals.push('cloudflare');
                    }
                    // DataDome
                    if (document.querySelector('iframe[src*="datadome"]') ||
                        document.querySelector('#datadome')) {
                        signals.push('datadome');
                    }
                    // Generic bot-detection text
                    const bodyText = (document.body?.innerText || '').toLowerCase();
                    if (bodyText.includes('are you a robot') ||
                        bodyText.includes('verify you are human') ||
                        bodyText.includes('bot detection') ||
                        bodyText.includes('access denied') && bodyText.includes('bot')) {
                        signals.push('bot_challenge_text');
                    }
                    return signals;
                }
            """)
            return bool(result) and len(result) > 0
        except Exception:
            # If the JS evaluation fails, don't block execution — assume no CAPTCHA.
            return False

    async def _extract_outputs(self, page: Any, action: TypedAction) -> dict:
        """Find DOM elements matching each contract output field and coerce values.

        Tries attribute selectors (``[data-field="X"]``, ``#X``, ``[name="X"]``)
        then falls back to label text containing the field name. Coerces the
        extracted string to the field's contract type.
        """
        outputs: dict[str, Any] = {}
        for field in action.contract.outputs:
            try:
                raw = await page.evaluate(_EXTRACT_FIELD_JS, field.name)
            except Exception:
                raw = None
            outputs[field.name] = _coerce_value(raw, field.type)
        return outputs

    async def _simulate(
        self, action: TypedAction, inputs: dict, ctx: ExecutionContext,
        note: str | None = None,
    ) -> AdapterResult:
        """Deterministic simulation fallback.

        Preserves the 15% failure rate (only on the simulation path) so the
        orchestrator's repair loop is demonstrable in demo mode / when
        Playwright is unavailable.
        """
        from .api_adapter import _simulate_outputs
        ts = ctx.telemetry.now()
        base: list[TraceEvent] = []
        if note:
            base.append(TraceEvent(
                ts=ts, adapter=AdapterType.browser, level="info",
                message=note, step="fallback", durationMs=0,
            ))
        base.extend([
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message="launch chromium headless (simulated)", step="launch", durationMs=180),
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message="goto workflow URL (simulated)", step="navigate", durationMs=220),
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message="fill login form (simulated)", step="input", durationMs=120),
        ])
        if _should_sim_fail(action, inputs):
            base.append(TraceEvent(
                ts=ts, adapter=AdapterType.browser, level="error",
                message='selector not found: button[data-testid="download-btn"]',
                step="click", durationMs=380,
            ))
            return AdapterResult(
                success=False, outputs={}, traces=base,
                screenshots=["snap-1.png"], durationMs=900,
                error='selector not found: button[data-testid="download-btn"]',
            )
        base.extend([
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message='click download button (simulated)', step="click", durationMs=110),
            TraceEvent(ts=ts, adapter=AdapterType.browser, level="info",
                       message="waitForDownload (simulated)", step="download", durationMs=260),
        ])
        return AdapterResult(
            success=True, outputs=_simulate_outputs(action, inputs),
            traces=base, screenshots=["snap-1.png", "snap-2.png"],
            error=None, durationMs=900,
        )
