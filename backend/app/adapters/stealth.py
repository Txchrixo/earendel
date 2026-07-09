"""Stealth evasions for the Playwright-backed BrowserAdapter.

These overrides mask the most common ``navigator.webdriver`` and Chromium
automation fingerprints so the headless browser looks like a real user
session to bot-detection scripts. The init script is injected via
``page.add_init_script(...)`` BEFORE any page navigation so it runs first
on every document load.

The module is dependency-free (no Playwright import) so it can be imported
even when Playwright is not installed — the constants are just strings.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Init script — 7 distinct evasions, each wrapped in try/catch so one
# failure doesn't break the whole init. Run via ``page.add_init_script``.
# ---------------------------------------------------------------------------
STEALTH_INIT_SCRIPT = r"""
(() => {
  // 1. Remove navigator.webdriver flag (the most common automation tell).
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  } catch (e) {}

  // 2. Override navigator.plugins to look non-empty (real Chrome ships 3).
  try {
    Object.defineProperty(navigator, 'plugins', {
      get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
      ],
    });
  } catch (e) {}

  // 3. Override navigator.languages to ['en-US', 'en'].
  try {
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
  } catch (e) {}

  // 4. Ensure window.chrome exists (headless Chromium may ship without it).
  try {
    if (!window.chrome) {
      window.chrome = {};
    }
  } catch (e) {}

  // 5. Ensure chrome.runtime exists (pages probe it for extension context).
  try {
    if (!window.chrome) window.chrome = {};
    if (!window.chrome.runtime) {
      window.chrome.runtime = {
        OnInstalledReason: { install: 'install', update: 'update', chrome_update: 'chrome_update', shared_module_update: 'shared_module_update' },
        PlatformOs: { mac: 'mac', win: 'win', android: 'android', cros: 'cros', linux: 'linux', openbsd: 'openbsd' },
        connect: () => {},
        sendMessage: () => {},
      };
    }
  } catch (e) {}

  // 6. Override permissions.query for notifications so detection scripts
  //    that expect a Notification permission response don't see a mismatch.
  try {
    const origQuery = window.navigator.permissions && window.navigator.permissions.query;
    if (origQuery) {
      window.navigator.permissions.query = (params) =>
        params && params.name === 'notifications'
          ? Promise.resolve({ state: typeof Notification !== 'undefined' ? Notification.permission : 'default' })
          : origQuery(params);
    }
  } catch (e) {}

  // 7. Override navigator.vendor to 'Google Inc.' (headless may report 'Google Inc.').
  try {
    Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
  } catch (e) {}
})();
"""

# Count of distinct overrides above — used in trace messages.
STEALTH_EVASION_COUNT = 7


# ---------------------------------------------------------------------------
# Chromium launch args — anti-detection + sandbox compatibility.
# ``--disable-blink-features=AutomationControlled`` is the headline evasion
# (strips the ``navigator.webdriver`` enable flag at the Blink level).
# ``--no-sandbox`` / ``--disable-setuid-sandbox`` are required to run
# headless Chromium inside containers/CI without SUID privileges.
# ---------------------------------------------------------------------------
STEALTH_LAUNCH_ARGS: list[str] = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--window-size=1280,720",
]


def build_proxy_config() -> dict[str, str] | None:
    """Read proxy env vars and return a Playwright proxy dict, or ``None``.

    Supports two forms:

    1. ``EARENDEL_BROWSER_PROXY`` — full URL with optional embedded creds,
       e.g. ``http://user:pass@host:port``. Parsed into
       ``{server, username?, password?}``.

    2. ``EARENDEL_BROWSER_PROXY_SERVER`` — just the server URL
       (``http://host:port``). Credentials may be supplied separately via
       ``EARENDEL_BROWSER_PROXY_USER`` and ``EARENDEL_BROWSER_PROXY_PASS``.

    Returns ``None`` if neither env var is set (Playwright then launches
    without a proxy).
    """
    full = os.environ.get("EARENDEL_BROWSER_PROXY", "").strip()
    if full:
        parsed = urlparse(full)
        if not parsed.scheme or not parsed.hostname:
            # Malformed — fall through to the server-only branch.
            pass
        else:
            cfg: dict[str, str] = {
                "server": f"{parsed.scheme}://{parsed.hostname}"
                + (f":{parsed.port}" if parsed.port else ""),
            }
            if parsed.username:
                cfg["username"] = parsed.username
            if parsed.password:
                cfg["password"] = parsed.password
            return cfg

    server = os.environ.get("EARENDEL_BROWSER_PROXY_SERVER", "").strip()
    if server:
        cfg = {"server": server}
        user = os.environ.get("EARENDEL_BROWSER_PROXY_USER", "").strip()
        pwd = os.environ.get("EARENDEL_BROWSER_PROXY_PASS", "").strip()
        if user:
            cfg["username"] = user
        if pwd:
            cfg["password"] = pwd
        return cfg

    return None
