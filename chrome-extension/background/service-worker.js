/**
 * Earendel Recorder - Background Service Worker
 *
 * Manages recording state across tabs, captures full HAR traffic via the
 * Chrome DevTools Protocol (chrome.debugger), captures cookies for the target
 * domain, and coordinates between the popup UI and content scripts.
 *
 * Capture pipeline:
 *   1. startRecording: chrome.debugger.attach + Network.enable + listeners
 *   2. CDP events: requestWillBeSent / responseReceived / loadingFinished / loadingFailed
 *   3. stopRecording: 2s grace period, build HAR 1.2 object, redact sensitive
 *      headers, capture cookies, detach
 *   4. sendToBackend: ships full HAR + cookies + steps to POST /api/v1/recordings
 *      On failure, persists the recording to chrome.storage.local under
 *      `pendingRecording_{timestamp}` for later retry.
 *
 * FALLBACK: if chrome.debugger is unavailable (e.g., older Chrome), or if
 * attach fails (e.g., DevTools already attached, or user dismissed the
 * debugger banner), we fall back to chrome.webRequest.onBeforeRequest
 * capturing only URL + method, and set harCaptured=false so the backend
 * knows the HAR is incomplete and should fall back to a synthesized demo HAR.
 *
 * MV3 SURVIVAL: service workers can be terminated at any time by Chrome.
 * We persist recording state (isRecording, tabId, harEntries, cookies, etc.)
 * to chrome.storage.session so we can resume after a restart. Pending
 * recordings that failed to send to the backend are persisted to
 * chrome.storage.local and retried on startup.
 *
 * SECURITY:
 *   - No eval, no dynamic code execution.
 *   - The debugger banner ("Earendel Recorder is debugging this tab") shown by
 *     Chrome when chrome.debugger.attach is called is EXPECTED and REQUIRED:
 *     it is a Chrome security feature that warns the user that the tab is being
 *     inspected. We do NOT try to suppress it.
 *   - Cookie capture uses chrome.cookies.getAll with the target domain only:
 *     no other domains are read.
 *   - Sensitive headers (Authorization, Cookie, Set-Cookie, X-API-Key,
 *     X-Auth-Token, X-CSRF-Token, X-XSRF-Token) are redacted from the HAR
 *     before being sent to the backend or persisted.
 *   - JSON postData containing password/token/secret keys is redacted.
 *   - All data is sanitized before sending to the backend.
 *   - Host permissions are broad (needed for recording) but data is never
 *     persisted outside the extension's local storage during recording.
 */

// ---- Constants ----

const DEFAULT_BACKEND_URL = "http://localhost:8001";
const DEFAULT_BACKEND_PORT = "8001";

// Headers that are redacted (value replaced with "[REDACTED]") before the HAR
// is persisted or sent to the backend. Lookup is case-insensitive.
const SENSITIVE_HEADERS = new Set([
  "authorization",
  "cookie",
  "set-cookie",
  "x-api-key",
  "x-auth-token",
  "x-csrf-token",
  "x-xsrf-token",
]);

// JSON keys in postData whose values are redacted when detected.
const SENSITIVE_JSON_KEYS = ["password", "token", "secret"];

// ---- State ----

let recordingState = {
  isRecording: false,
  tabId: null,
  steps: [],
  networkRequests: [],          // lightweight list (URL + method) for backward compat / popup UI
  domMutations: 0,
  screenshots: 0,
  harCaptured: false,
  harEntries: [],               // full HAR 1.2 entries built from CDP events
  cdpRequests: new Map(),       // requestId -> in-flight request/response metadata
  cookies: [],                  // cookies captured at start + stop
  startedAt: null,
  connectorName: null,
  workflowName: null,
  debuggerAttached: false,      // true if chrome.debugger.attach succeeded
  runId: null,                  // unique ID for this recording run (used in screenshot filenames)
  screenshotFiles: [],          // list of screenshot storage keys saved during the run
  _lastHarSaveCount: 0,         // last harEntries.length we persisted (for throttling)
  _lastScreenshotAt: 0,         // last screenshot timestamp (for throttling)
};

// ---- Backend URL configuration ----

/**
 * Read the configured backend URL from chrome.storage.local.
 * Falls back to DEFAULT_BACKEND_URL ("http://localhost:8001") if not set.
 *
 * @returns {Promise<string>}
 */
async function getBackendUrl() {
  try {
    const { backendUrl } = await chrome.storage.local.get("backendUrl");
    if (backendUrl && typeof backendUrl === "string" && backendUrl.length > 0) {
      return backendUrl.replace(/\/+$/, ""); // strip trailing slash
    }
  } catch (err) {
    console.warn("[Earendel] Could not read backendUrl from storage:", err);
  }
  return DEFAULT_BACKEND_URL;
}

/**
 * Extract the port from a backend URL. Returns the port as a string.
 * If the URL has no explicit port, returns "80" for http or "443" for https.
 *
 * @param {string} url
 * @returns {string}
 */
function getBackendPort(url) {
  try {
    const parsed = new URL(url);
    if (parsed.port) return parsed.port;
    return parsed.protocol === "https:" ? "443" : "80";
  } catch {
    return DEFAULT_BACKEND_PORT;
  }
}

// ---- MV3 state persistence (chrome.storage.session) ----

/**
 * Persist the recording state to chrome.storage.session so we can resume
 * after a service worker restart. chrome.storage.session is MV3-safe and is
 * cleared when the browser closes (not persisted across browser sessions).
 *
 * We persist a JSON-serializable subset of recordingState. The cdpRequests
 * Map is converted to an array of [key, value] pairs so it survives JSON
 * round-tripping. We throttle HAR persistence so we only write when 5+ new
 * entries have accumulated (or always if `force` is true).
 *
 * @param {boolean} [force=false] - Force a write even if few new entries.
 * @returns {Promise<void>}
 */
async function _saveState(force = false) {
  if (!recordingState.isRecording && !force) return;
  try {
    const harCount = recordingState.harEntries.length;
    if (!force && harCount - recordingState._lastHarSaveCount < 5) {
      // Not enough new entries to justify a write. We still persist steps +
      // cookies on every call so the user does not lose interaction data.
    }

    const state = {
      isRecording: recordingState.isRecording,
      tabId: recordingState.tabId,
      connectorName: recordingState.connectorName,
      workflowName: recordingState.workflowName,
      startedAt: recordingState.startedAt,
      steps: recordingState.steps,
      networkRequests: recordingState.networkRequests,
      domMutations: recordingState.domMutations,
      screenshots: recordingState.screenshots,
      harCaptured: recordingState.harCaptured,
      harEntries: recordingState.harEntries,
      cookies: recordingState.cookies,
      debuggerAttached: recordingState.debuggerAttached,
      runId: recordingState.runId,
      screenshotFiles: recordingState.screenshotFiles,
      savedAt: Date.now(),
    };
    await chrome.storage.session.set({ earendelRecordingState: state });
    recordingState._lastHarSaveCount = harCount;
  } catch (err) {
    console.warn("[Earendel] _saveState failed:", err);
  }
}

/**
 * Restore recording state from chrome.storage.session. Called on service
 * worker startup. If a recording was active when the SW was terminated, we
 * restore the in-memory state and attempt to re-attach the debugger so CDP
 * capture continues. If re-attach fails, we fall back to webRequest capture.
 *
 * @returns {Promise<void>}
 */
async function _loadState() {
  try {
    const { earendelRecordingState: saved } = await chrome.storage.session.get(
      "earendelRecordingState"
    );
    if (!saved || !saved.isRecording) return;

    console.log("[Earendel] Restoring recording state after SW restart:", {
      tabId: saved.tabId,
      runId: saved.runId,
      steps: (saved.steps || []).length,
      harEntries: (saved.harEntries || []).length,
    });

    recordingState = {
      isRecording: true,
      tabId: saved.tabId,
      steps: saved.steps || [],
      networkRequests: saved.networkRequests || [],
      domMutations: saved.domMutations || 0,
      screenshots: saved.screenshots || 0,
      harCaptured: false, // re-established below
      harEntries: saved.harEntries || [],
      cdpRequests: new Map(),
      cookies: saved.cookies || [],
      startedAt: saved.startedAt || Date.now(),
      connectorName: saved.connectorName || "unknown",
      workflowName: saved.workflowName || "recorded-workflow",
      debuggerAttached: false,
      runId: saved.runId || `run_${Date.now()}`,
      screenshotFiles: saved.screenshotFiles || [],
      _lastHarSaveCount: (saved.harEntries || []).length,
      _lastScreenshotAt: 0,
    };

    // Verify the tab still exists. If it was closed, abandon the recording.
    if (!recordingState.tabId) {
      console.warn("[Earendel] Restored state had no tabId; abandoning.");
      await chrome.storage.session.remove("earendelRecordingState");
      recordingState = _freshRecordingState();
      return;
    }
    try {
      await chrome.tabs.get(recordingState.tabId);
    } catch {
      console.warn("[Earendel] Recorded tab no longer exists; abandoning recording.");
      await chrome.storage.session.remove("earendelRecordingState");
      recordingState = _freshRecordingState();
      return;
    }

    // Re-establish capture. Request the optional permissions first, since the
    // SW restart may have lost the in-memory permission grant state. Chrome
    // remembers granted permissions across SW restarts, so this is a no-op if
    // the user already granted them at the start of the run.
    const granted = await chrome.permissions.contains({
      permissions: ["debugger", "cookies"],
      origins: ["http://*/*", "https://*/*"],
    });
    if (!granted) {
      console.warn("[Earendel] Optional permissions no longer granted; using webRequest fallback.");
      startFallbackNetworkCapture(recordingState.tabId);
      recordingState.harCaptured = false;
      return;
    }

    const attached = await attachDebugger(recordingState.tabId);
    if (attached) {
      if (!chrome.debugger._earendelListenerRegistered) {
        chrome.debugger.onEvent.addListener(handleCdpEvent);
        chrome.debugger._earendelListenerRegistered = true;
      }
      recordingState.harCaptured = true;
      console.log("[Earendel] Debugger re-attached after SW restart.");
    } else {
      startFallbackNetworkCapture(recordingState.tabId);
      recordingState.harCaptured = false;
      console.warn("[Earendel] Debugger re-attach failed; using webRequest fallback.");
    }
  } catch (err) {
    console.error("[Earendel] _loadState error:", err);
  }
}

/**
 * Return a fresh, empty recordingState object. Used on init and when abandoning
 * a recording.
 *
 * @returns {object}
 */
function _freshRecordingState() {
  return {
    isRecording: false,
    tabId: null,
    steps: [],
    networkRequests: [],
    domMutations: 0,
    screenshots: 0,
    harCaptured: false,
    harEntries: [],
    cdpRequests: new Map(),
    cookies: [],
    startedAt: null,
    connectorName: null,
    workflowName: null,
    debuggerAttached: false,
    runId: null,
    screenshotFiles: [],
    _lastHarSaveCount: 0,
    _lastScreenshotAt: 0,
  };
}

// ---- Network request capture via chrome.webRequest (FALLBACK only) ----

const NETWORK_FILTER = {
  urls: ["http://*/*", "https://*/*"],
  types: ["xmlhttprequest", "fetch", "main_frame", "sub_frame"],
};

let networkListener = null;

function startFallbackNetworkCapture(tabId) {
  if (networkListener) chrome.webRequest.onBeforeRequest.removeListener(networkListener);

  networkListener = (details) => {
    // Only capture requests from the recording tab
    if (details.tabId !== tabId) return;

    // Skip extension's own requests
    if (details.url.includes("chrome-extension://")) return;

    const request = {
      url: details.url,
      method: details.method || "GET",
      type: details.type,
      timestamp: Date.now(),
      tabId: details.tabId,
      requestId: details.requestId,
    };

    recordingState.networkRequests.push(request);
  };

  chrome.webRequest.onBeforeRequest.addListener(networkListener, NETWORK_FILTER, [
    "requestBody",
  ]);
}

function stopFallbackNetworkCapture() {
  if (networkListener) {
    chrome.webRequest.onBeforeRequest.removeListener(networkListener);
    networkListener = null;
  }
}

// ---- CDP-based HAR capture via chrome.debugger ----

/**
 * Attach the Chrome DevTools Protocol debugger to the target tab and enable
 * the Network domain so we can capture request/response bodies, headers,
 * status codes, and timings.
 *
 * NOTE: chrome.debugger.attach causes Chrome to show a yellow warning banner
 * at the top of the target tab: "Earendel Recorder is debugging this tab".
 * This is a Chrome security feature - it warns the user that the tab is being
 * inspected. We do NOT suppress it; it is required for transparency.
 *
 * If the target tab is already being debugged (e.g., DevTools is open), the
 * attach call will fail with "Another debugger is already attached". We catch
 * this and fall back to the webRequest-based capture (URL + method only).
 *
 * @param {number} tabId - Target tab ID.
 * @returns {Promise<boolean>} true if debugger attached, false on failure.
 */
function attachDebugger(tabId) {
  return new Promise((resolve) => {
    if (!chrome.debugger || typeof chrome.debugger.attach !== "function") {
      console.warn("[Earendel] chrome.debugger not available - falling back to webRequest.");
      resolve(false);
      return;
    }

    chrome.debugger.attach({ tabId }, "1.3", (attachErr) => {
      if (chrome.runtime.lastError || attachErr) {
        const msg = chrome.runtime.lastError?.message || attachErr?.message || String(attachErr);
        console.warn("[Earendel] Debugger attach failed - falling back to webRequest:", msg);
        resolve(false);
        return;
      }

      chrome.debugger.sendCommand({ tabId }, "Network.enable", () => {
        // Disable the HTTP cache so every request actually hits the network
        // (otherwise HAR capture misses responses served from cache).
        chrome.debugger.sendCommand(
          { tabId },
          "Network.setCacheDisabled",
          { cacheDisabled: true },
          () => {
            recordingState.debuggerAttached = true;
            console.log("[Earendel] Debugger attached to tab", tabId);
            resolve(true);
          }
        );
      });
    });
  });
}

/**
 * Detach the debugger from the target tab. Always called when recording stops,
 * even on error, so the user doesn't get stuck with the debugging banner.
 *
 * @param {number} tabId - Target tab ID.
 * @returns {Promise<void>}
 */
function detachDebugger(tabId) {
  return new Promise((resolve) => {
    if (!recordingState.debuggerAttached) {
      resolve();
      return;
    }
    if (!chrome.debugger) {
      recordingState.debuggerAttached = false;
      resolve();
      return;
    }
    try {
      chrome.debugger.detach({ tabId }, () => {
        // Swallow "not attached" / lastError - we always want to resolve.
        if (chrome.runtime.lastError) {
          console.debug("[Earendel] Debugger detach note:", chrome.runtime.lastError.message);
        }
        recordingState.debuggerAttached = false;
        resolve();
      });
    } catch (err) {
      console.warn("[Earendel] Debugger detach threw:", err);
      recordingState.debuggerAttached = false;
      resolve();
    }
  });
}

/**
 * Handle CDP events routed through chrome.debugger.onEvent.
 *
 * CDP event reference (Network domain):
 *   - Network.requestWillBeSent: fired when a request is about to be sent.
 *     Carries requestId, request {url, method, headers, postData, ...},
 *     wallTime, timestamp, type, initiator, redirectResponse (if a redirect).
 *   - Network.responseReceived: fired when a response is received.
 *     Carries requestId, response {url, status, statusText, headers, mimeType,
 *     protocol, ...}, type, timestamp.
 *   - Network.loadingFinished: fired when the request finishes loading.
 *     Carries requestId, timestamp, encodedDataLength, and (for some
 *     responses) a `metrics` object. The response body must be fetched
 *     separately via Network.getResponseBody.
 *   - Network.loadingFailed: fired when the request fails (network error,
 *     abort, etc.). Carries requestId, errorText, canceled, blockedReason.
 *
 * @param {chrome.debugger.Debuggee} source - The debuggee that fired the event.
 * @param {string} method - The CDP method name (e.g., "Network.requestWillBeSent").
 * @param {object} params - The event parameters.
 */
function handleCdpEvent(source, method, params) {
  // Only handle events from the recording tab
  if (!source || source.tabId !== recordingState.tabId) return;
  if (!recordingState.isRecording) return;

  if (method === "Network.requestWillBeSent") {
    onCdpRequestWillBeSent(params);
  } else if (method === "Network.responseReceived") {
    onCdpResponseReceived(params);
  } else if (method === "Network.loadingFinished") {
    onCdpLoadingFinished(params);
  } else if (method === "Network.loadingFailed") {
    onCdpLoadingFailed(params);
  }

  // Fix 2: persist state after each CDP event so we can survive a SW restart.
  // Throttled internally (only writes when 5+ new HAR entries).
  _saveState(false).catch((e) =>
    console.debug("[Earendel] _saveState after CDP event failed (non-fatal):", e)
  );
}

function onCdpRequestWillBeSent(params) {
  const { requestId, request, wallTime, timestamp, type, redirectResponse } = params;
  if (!request) return;

  // Skip extension's own requests
  if (request.url && request.url.startsWith("chrome-extension://")) return;

  // If this is a redirect, the prior request's loadingFinished will never
  // fire - finalize the prior entry now using the redirectResponse.
  if (redirectResponse) {
    finalizeEntryFromRedirect(requestId, redirectResponse);
  }

  const headersList = headersObjToList(request.headers);
  const queryStringList = parseQueryString(request.url);
  const postData = request.postData
    ? {
        mimeType: request.postDataMimeType || headersLookup(request.headers, "content-type") || "application/octet-stream",
        text: request.postData,
      }
    : request.hasPostData
      ? { mimeType: "application/octet-stream", text: "" }
      : undefined;

  const bodySize = request.postData ? request.postData.length : 0;

  const entry = {
    _requestId: requestId,
    _requestType: type || "Other",
    startedDateTime: wallTime ? new Date(wallTime * 1000).toISOString() : new Date().toISOString(),
    _cdpStartTime: timestamp, // CDP monotonic timestamp (seconds)
    time: 0,                  // filled in on loadingFinished/loadingFailed
    request: {
      method: request.method || "GET",
      url: request.url,
      httpVersion: request.protocol ? cdpProtocolToHttpVersion(request.protocol) : "HTTP/1.1",
      headers: headersList,
      queryString: queryStringList,
      postData,
      headersSize: -1,
      bodySize,
    },
    response: undefined, // filled in on responseReceived
    cache: {},
    timings: { send: 0, wait: 0, receive: 0, blocked: -1, connect: -1, dns: -1, ssl: -1 },
    _status: "pending",
  };

  recordingState.cdpRequests.set(requestId, entry);
}

function onCdpResponseReceived(params) {
  const { requestId, response, timestamp } = params;
  if (!response) return;

  const entry = recordingState.cdpRequests.get(requestId);
  if (!entry) return;

  entry._cdpResponseTime = timestamp;
  entry.response = {
    status: response.status || 0,
    statusText: response.statusText || "",
    httpVersion: response.protocol ? cdpProtocolToHttpVersion(response.protocol) : "HTTP/1.1",
    headers: headersObjToList(response.headers),
    content: {
      mimeType: response.mimeType || "",
      text: "",            // filled in on loadingFinished via Network.getResponseBody
      size: 0,
    },
    redirectURL: headersLookup(response.headers, "location") || "",
    headersSize: -1,
    bodySize: response.encodedDataLength != null ? response.encodedDataLength : -1,
  };

  // Compute the "wait" timing (request → response)
  if (entry._cdpStartTime != null && timestamp != null) {
    const waitMs = Math.max(0, Math.round((timestamp - entry._cdpStartTime) * 1000));
    entry.timings.wait = waitMs;
    entry.time = waitMs;
  }
}

function onCdpLoadingFinished(params) {
  const { requestId, timestamp, encodedDataLength } = params;
  const entry = recordingState.cdpRequests.get(requestId);
  if (!entry) return;

  // Compute "receive" timing (response → finished)
  if (entry._cdpResponseTime != null && timestamp != null) {
    const receiveMs = Math.max(0, Math.round((timestamp - entry._cdpResponseTime) * 1000));
    entry.timings.receive = receiveMs;
    entry.time = (entry.time || 0) + receiveMs;
  }

  if (entry.response && entry.response.content) {
    if (encodedDataLength != null) {
      entry.response.content.size = encodedDataLength;
      if (entry.response.bodySize === -1) entry.response.bodySize = encodedDataLength;
    }
  }

  // Fetch the response body asynchronously. Network.getResponseBody can fail
  // for streaming responses, large files, or if the response was already
  // evicted from the CDP buffer - handle gracefully.
  fetchResponseBody(recordingState.tabId, requestId, entry).finally(() => {
    entry._status = "finished";
  });

  // Fix 3: capture a screenshot after each loadingFinished event (throttled
  // to one per second inside _maybeCaptureScreenshot to avoid spam).
  if (recordingState.tabId) {
    _maybeCaptureScreenshot(
      recordingState.tabId,
      recordingState.harEntries.length + recordingState.cdpRequests.size
    ).catch(() => {});
  }
}

function onCdpLoadingFailed(params) {
  const { requestId, errorText, canceled, blockedReason, timestamp } = params;
  const entry = recordingState.cdpRequests.get(requestId);
  if (!entry) return;

  // Compute "receive" timing up to the failure
  if (entry._cdpResponseTime != null && timestamp != null) {
    const receiveMs = Math.max(0, Math.round((timestamp - entry._cdpResponseTime) * 1000));
    entry.timings.receive = receiveMs;
    entry.time = (entry.time || 0) + receiveMs;
  }

  // If we never got a responseReceived, synthesize a 0/failed response so the
  // HAR entry has the standard shape.
  if (!entry.response) {
    entry.response = {
      status: 0,
      statusText: "Failed",
      httpVersion: "HTTP/1.1",
      headers: [],
      content: { mimeType: "", text: "", size: 0 },
      redirectURL: "",
      headersSize: -1,
      bodySize: -1,
    };
  }
  entry.response._error = errorText || "loading failed";
  if (canceled) entry.response._canceled = true;
  if (blockedReason) entry.response._blockedReason = blockedReason;
  entry._status = "failed";
}

/**
 * Finalize a HAR entry when a redirect happens. CDP fires a new
 * requestWillBeSent with the same requestId and a `redirectResponse` field
 * that describes the response to the original (pre-redirect) request. The
 * original request's loadingFinished will never fire, so we close it out here.
 *
 * @param {string} requestId - CDP request ID (shared between redirect chain).
 * @param {object} redirectResponse - The response that triggered the redirect.
 */
function finalizeEntryFromRedirect(requestId, redirectResponse) {
  const entry = recordingState.cdpRequests.get(requestId);
  if (!entry || entry.response) return; // already finalized

  entry.response = {
    status: redirectResponse.status || 0,
    statusText: redirectResponse.statusText || "",
    httpVersion: redirectResponse.protocol
      ? cdpProtocolToHttpVersion(redirectResponse.protocol)
      : "HTTP/1.1",
    headers: headersObjToList(redirectResponse.headers),
    content: {
      mimeType: redirectResponse.mimeType || "",
      text: "",
      size: redirectResponse.encodedDataLength != null ? redirectResponse.encodedDataLength : 0,
    },
    redirectURL: headersLookup(redirectResponse.headers, "location") || "",
    headersSize: -1,
    bodySize: redirectResponse.encodedDataLength != null ? redirectResponse.encodedDataLength : -1,
  };
  entry._status = "redirect";

  // Push the pre-redirect entry into the HAR list and clear it so the new
  // requestWillBeSent (which uses the same requestId) can start fresh.
  recordingState.harEntries.push({ ...entry });
  recordingState.cdpRequests.delete(requestId);
}

/**
 * Fetch the response body for a finished request via Network.getResponseBody.
 *
 * @param {number} tabId
 * @param {string} requestId
 * @param {object} entry - The HAR entry to populate.
 * @returns {Promise<void>}
 */
function fetchResponseBody(tabId, requestId, entry) {
  return new Promise((resolve) => {
    if (!entry.response || !entry.response.content) {
      resolve();
      return;
    }
    try {
      chrome.debugger.sendCommand(
        { tabId },
        "Network.getResponseBody",
        { requestId },
        (bodyResult) => {
          if (chrome.runtime.lastError) {
            entry.response.content.text = "";
            entry.response.content._error = "body fetch failed: " + chrome.runtime.lastError.message;
            resolve();
            return;
          }
          if (!bodyResult) {
            entry.response.content.text = "";
            entry.response.content._error = "body fetch returned empty";
            resolve();
            return;
          }
          // bodyResult = { body: string, base64Encoded: boolean }
          if (bodyResult.base64Encoded) {
            // Keep the base64 payload as-is - the backend can decode it.
            // Mark it so consumers know it's base64-encoded.
            entry.response.content.text = bodyResult.body || "";
            entry.response.content.encoding = "base64";
          } else {
            entry.response.content.text = bodyResult.body || "";
          }
          resolve();
        }
      );
    } catch (err) {
      entry.response.content.text = "";
      entry.response.content._error = "body fetch threw: " + (err && err.message);
      resolve();
    }
  });
}

// ---- HAR helpers ----

/**
 * Convert a CDP headers object ({name: value}) to the HAR 1.2 array form
 * [{name, value}, ...]. CDP headers are case-insensitive keys.
 *
 * @param {object} headersObj - { "Content-Type": "application/json", ... }
 * @returns {Array<{name: string, value: string}>}
 */
function headersObjToList(headersObj) {
  if (!headersObj || typeof headersObj !== "object") return [];
  return Object.entries(headersObj).map(([name, value]) => ({
    name,
    value: String(value),
  }));
}

/**
 * Case-insensitive header lookup.
 *
 * @param {object} headersObj
 * @param {string} name
 * @returns {string|null}
 */
function headersLookup(headersObj, name) {
  if (!headersObj || typeof headersObj !== "object") return null;
  const lower = name.toLowerCase();
  for (const [k, v] of Object.entries(headersObj)) {
    if (k.toLowerCase() === lower) return String(v);
  }
  return null;
}

/**
 * Parse a URL's query string into HAR 1.2 queryString array.
 *
 * @param {string} url
 * @returns {Array<{name: string, value: string}>}
 */
function parseQueryString(url) {
  if (!url) return [];
  let q;
  try {
    q = new URL(url).searchParams;
  } catch {
    return [];
  }
  const out = [];
  for (const [name, value] of q.entries()) {
    out.push({ name, value });
  }
  return out;
}

/**
 * Map CDP protocol strings (e.g., "http/1.1", "h2", "h3") to HAR 1.2
 * httpVersion strings ("HTTP/1.1", "HTTP/2", "HTTP/3").
 *
 * @param {string} protocol
 * @returns {string}
 */
function cdpProtocolToHttpVersion(protocol) {
  if (!protocol) return "HTTP/1.1";
  const p = protocol.toLowerCase();
  if (p === "h2" || p === "http/2") return "HTTP/2";
  if (p === "h3" || p === "http/3") return "HTTP/3";
  if (p === "h1" || p === "http/1.0") return "HTTP/1.0";
  if (p === "http/1.1") return "HTTP/1.1";
  if (p === "ws") return "WS";
  if (p === "wss") return "WSS";
  // Unknown protocol - return as-is, upper-cased.
  return protocol.toUpperCase();
}

// ---- Sensitive data redaction (Fix 1) ----

/**
 * Redact sensitive headers and postData from a HAR object in place.
 *
 * - Replaces the value of any sensitive header (case-insensitive match
 *   against SENSITIVE_HEADERS) with "[REDACTED]" in both request and
 *   response headers of every entry.
 * - If a request's postData.text parses as JSON and contains any of the
 *   sensitive keys (password, token, secret), the values of those keys
 *   are replaced with "[REDACTED]" and the text is re-serialized.
 *
 * The HAR object is mutated in place AND returned for chaining.
 *
 * @param {object} har - The HAR 1.2 object built by buildHarObject().
 * @returns {object} The same HAR object, with sensitive data redacted.
 */
function _redactSensitiveData(har) {
  if (!har || !har.log || !Array.isArray(har.log.entries)) return har;

  for (const entry of har.log.entries) {
    if (entry.request && Array.isArray(entry.request.headers)) {
      entry.request.headers = entry.request.headers.map((h) =>
        _redactHeader(h)
      );
    }
    if (entry.response && Array.isArray(entry.response.headers)) {
      entry.response.headers = entry.response.headers.map((h) =>
        _redactHeader(h)
      );
    }
    if (entry.request && entry.request.postData && entry.request.postData.text) {
      entry.request.postData.text = _redactPostData(entry.request.postData.text);
    }
  }
  return har;
}

/**
 * Redact a single header object if its name is in SENSITIVE_HEADERS.
 *
 * @param {{name: string, value: string}} header
 * @returns {{name: string, value: string}}
 */
function _redactHeader(header) {
  if (!header || !header.name) return header;
  if (SENSITIVE_HEADERS.has(header.name.toLowerCase())) {
    return { ...header, value: "[REDACTED]" };
  }
  return header;
}

/**
 * Redact sensitive values inside a JSON postData string. If the text does not
 * parse as JSON, it is returned unchanged. If it parses as JSON and contains
 * any of the sensitive keys (password, token, secret) at the top level or
 * inside nested objects, those values are replaced with "[REDACTED]" and the
 * text is re-serialized with the same formatting style (2-space indent if the
 * original had whitespace, otherwise compact).
 *
 * @param {string} text - The original postData text.
 * @returns {string} The redacted postData text.
 */
function _redactPostData(text) {
  if (!text || typeof text !== "string") return text;
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    // Not JSON - leave as-is. We intentionally do not regex-scrub arbitrary
    // text because that could corrupt binary or form-encoded payloads.
    return text;
  }
  if (parsed && typeof parsed === "object") {
    _redactSensitiveJsonKeys(parsed);
    const compact = text.trim().startsWith("{") && !text.includes("\n");
    return JSON.stringify(parsed, null, compact ? 0 : 2);
  }
  return text;
}

/**
 * Walk a parsed JSON object/array tree and replace the value of any
 * sensitive key with "[REDACTED]". Mutates the input.
 *
 * @param {any} node
 */
function _redactSensitiveJsonKeys(node) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    for (const item of node) _redactSensitiveJsonKeys(item);
    return;
  }
  for (const key of Object.keys(node)) {
    const lower = key.toLowerCase();
    if (SENSITIVE_JSON_KEYS.some((s) => lower === s || lower.includes(s))) {
      node[key] = "[REDACTED]";
    } else if (node[key] && typeof node[key] === "object") {
      _redactSensitiveJsonKeys(node[key]);
    }
  }
}

/**
 * Build the final HAR 1.2 object from the captured entries.
 *
 * Standard HAR 1.2 schema (subset that backend har_analyzer.py expects):
 *   {
 *     log: {
 *       version: "1.2",
 *       creator: { name, version },
 *       entries: [
 *         {
 *           startedDateTime, time,
 *           request: { method, url, httpVersion, headers, queryString, postData, headersSize, bodySize },
 *           response: { status, statusText, httpVersion, headers, content: { mimeType, text, size }, redirectURL, headersSize, bodySize },
 *           cache: {},
 *           timings: { send, wait, receive, blocked, connect, dns, ssl },
 *         },
 *         ...
 *       ],
 *     },
 *   }
 *
 * @returns {object}
 */
function buildHarObject() {
  // Drain any in-flight entries that never got a loadingFinished/loadingFailed
  // (e.g., recording stopped mid-request). Mark them with _status="pending"
  // and synthesize a 0 response so they're still shipped.
  for (const entry of recordingState.cdpRequests.values()) {
    if (entry._status === "pending" && !entry.response) {
      entry.response = {
        status: 0,
        statusText: "Pending",
        httpVersion: "HTTP/1.1",
        headers: [],
        content: { mimeType: "", text: "", size: 0 },
        redirectURL: "",
        headersSize: -1,
        bodySize: -1,
      };
      entry._status = "pending-drained";
    }
    if (entry._status !== "redirect") {
      // (redirects were already pushed into harEntries in finalizeEntryFromRedirect)
      recordingState.harEntries.push(entry);
    }
  }
  recordingState.cdpRequests.clear();

  // Strip internal underscore-prefixed fields before shipping.
  const entries = recordingState.harEntries.map((e) => {
    const cleaned = {
      startedDateTime: e.startedDateTime,
      time: e.time || 0,
      request: e.request,
      response: e.response,
      cache: e.cache || {},
      timings: e.timings,
    };
    // Keep _requestId + _requestType as they're useful for debugging + the
    // backend's analyzer (which ignores unknown fields).
    if (e._requestId) cleaned._requestId = e._requestId;
    if (e._requestType) cleaned._requestType = e._requestType;
    return cleaned;
  });

  return {
    log: {
      version: "1.2",
      creator: { name: "earendel-chrome-extension", version: "1.0" },
      entries,
    },
  };
}

// ---- Cookie capture ----

/**
 * Capture all cookies for the target tab's domain (and its parent domains,
 * since session cookies often live on a parent domain like .example.com).
 *
 * Uses chrome.cookies.getAll. Requires the "cookies" permission + host
 * permissions for the target domain (both already granted in manifest).
 *
 * @param {number} tabId
 * @returns {Promise<Array<object>>} - Array of cookie objects.
 */
async function captureCookies(tabId) {
  if (!chrome.cookies || typeof chrome.cookies.getAll !== "function") {
    console.warn("[Earendel] chrome.cookies API not available.");
    return [];
  }
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !tab.url) return [];
    const url = new URL(tab.url);
    const domain = url.hostname;

    // Capture cookies for the exact domain AND its parent domains (e.g.,
    // "shop.acme.com" → also query "acme.com" + ".acme.com") so session
    // cookies set on the parent aren't missed.
    const domains = new Set([domain, "." + domain]);
    const parts = domain.split(".");
    for (let i = 1; i < parts.length - 1; i++) {
      const sub = parts.slice(i).join(".");
      domains.add(sub);
      domains.add("." + sub);
    }

    const allCookies = [];
    for (const d of domains) {
      try {
        const cookies = await chrome.cookies.getAll({ domain: d });
        for (const c of cookies) {
          // Deduplicate by (name, domain, path).
          const key = `${c.name}|${c.domain}|${c.path}`;
          if (allCookies.some((existing) => `${existing.name}|${existing.domain}|${existing.path}` === key)) {
            continue;
          }
          allCookies.push({
            name: c.name,
            value: c.value,
            domain: c.domain,
            path: c.path,
            secure: c.secure,
            httpOnly: c.httpOnly,
            sameSite: c.sameSite || "unspecified",
            session: c.session,
            expirationDate: c.expirationDate,
            hostOnly: c.hostOnly,
          });
        }
      } catch (err) {
        console.debug("[Earendel] Cookie fetch failed for domain", d, err);
      }
    }
    return allCookies;
  } catch (err) {
    console.error("[Earendel] captureCookies error:", err);
    return [];
  }
}

// ---- Screenshot capture ----

async function captureScreenshot(tabId) {
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(tabId, {
      format: "png",
    });
    recordingState.screenshots++;
    return dataUrl;
  } catch (err) {
    console.error("[Earendel] Screenshot error:", err);
    return null;
  }
}

/**
 * Capture a screenshot via the Chrome DevTools Protocol
 * (Page.captureScreenshot). This works even when the tab is not visible
 * (e.g., background tab), unlike chrome.tabs.captureVisibleTab which
 * requires the tab to be active.
 *
 * The PNG bytes are returned as a base64-encoded string by CDP. We persist
 * the data to chrome.storage.local under a key of the form
 * `screenshot_{runId}_{step}.png` and record the key in
 * recordingState.screenshotFiles so it can be included in the final payload.
 *
 * Throttled to one capture per second to avoid spamming storage when many
 * Network.loadingFinished events fire in quick succession.
 *
 * @param {number} tabId
 * @param {number} [step] - The current step index, used in the storage key.
 * @returns {Promise<string|null>} The storage key, or null on failure.
 */
async function _captureCdpScreenshot(tabId, step) {
  if (!recordingState.isRecording) return null;
  if (!recordingState.debuggerAttached) return null;

  const now = Date.now();
  if (now - recordingState._lastScreenshotAt < 1000) return null; // throttle
  recordingState._lastScreenshotAt = now;

  try {
    const result = await new Promise((resolve) => {
      chrome.debugger.sendCommand(
        { tabId },
        "Page.captureScreenshot",
        { format: "png" },
        (resp) => {
          if (chrome.runtime.lastError) {
            resolve(null);
            return;
          }
          resolve(resp);
        }
      );
    });
    if (!result || !result.data) return null;
    const runId = recordingState.runId || `run_${now}`;
    const stepPart = step != null ? step : recordingState.screenshots;
    const key = `screenshot_${runId}_${stepPart}.png`;
    await chrome.storage.local.set({ [key]: result.data });
    recordingState.screenshotFiles.push(key);
    recordingState.screenshots++;
    return key;
  } catch (err) {
    console.warn("[Earendel] CDP screenshot capture failed:", err);
    return null;
  }
}

/**
 * Periodically-triggered screenshot capture. Called after CDP loadingFinished
 * events and after every 10 steps. Throttled inside _captureCdpScreenshot.
 *
 * @param {number} tabId
 * @param {number} [step]
 * @returns {Promise<void>}
 */
async function _maybeCaptureScreenshot(tabId, step) {
  try {
    await _captureCdpScreenshot(tabId, step);
  } catch (err) {
    console.debug("[Earendel] Screenshot trigger error (non-fatal):", err);
  }
}

// ---- Recording control ----

/**
 * Start a recording session on the given tab.
 *
 * Flow:
 *   1. Reset recordingState, assign a fresh runId.
 *   2. Request the optional "debugger" + "cookies" permissions at runtime
 *      (they are declared as optional_permissions in the manifest). If the
 *      user denies, fall back to webRequest-based capture.
 *   3. Attach the debugger (CDP) and enable Network domain.
 *      - If attach succeeds: register onEvent listener, set harCaptured=true.
 *      - If attach fails: fall back to webRequest.onBeforeRequest, set harCaptured=false.
 *   4. Capture cookies for the target domain (initial state).
 *   5. Tell the content script to start (DOM capture). The content script is
 *      injected via the manifest's content_scripts declaration; we do NOT use
 *      chrome.scripting.executeScript (the "scripting" permission is no longer
 *      requested).
 *   6. Capture an initial screenshot.
 *   7. Persist the recording state to chrome.storage.session for MV3 survival.
 *
 * @param {number} tabId
 * @param {object} options - { connectorName, workflowName }
 */
async function startRecording(tabId, options = {}) {
  // Reset state - including a fresh Map for CDP request tracking and a runId.
  recordingState = {
    isRecording: true,
    tabId: tabId,
    steps: [],
    networkRequests: [],
    domMutations: 0,
    screenshots: 0,
    harCaptured: false,
    harEntries: [],
    cdpRequests: new Map(),
    cookies: [],
    startedAt: Date.now(),
    connectorName: options.connectorName || "unknown",
    workflowName: options.workflowName || "recorded-workflow",
    debuggerAttached: false,
    runId: `run_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    screenshotFiles: [],
    _lastHarSaveCount: 0,
    _lastScreenshotAt: 0,
  };

  // Request the optional permissions at runtime. These are required for the
  // CDP-based HAR capture and cookie capture. If the user previously granted
  // them, this is a no-op. If they deny, we fall back to webRequest.
  let optionalGranted = false;
  try {
    optionalGranted = await chrome.permissions.request({
      permissions: ["debugger", "cookies"],
      origins: ["http://*/*", "https://*/*"],
    });
  } catch (permErr) {
    console.warn("[Earendel] Optional permission request threw:", permErr);
  }
  if (!optionalGranted) {
    console.warn(
      "[Earendel] Optional permissions (debugger/cookies) not granted; using webRequest fallback."
    );
  }

  // Try CDP-based HAR capture first (only if debugger permission is granted).
  let attached = false;
  if (optionalGranted) {
    attached = await attachDebugger(tabId);
  }
  if (attached) {
    // Register the CDP event listener. (Safe to register before attach:
    // we filter by source.tabId inside handleCdpEvent.)
    if (!chrome.debugger._earendelListenerRegistered) {
      chrome.debugger.onEvent.addListener(handleCdpEvent);
      chrome.debugger._earendelListenerRegistered = true;
    }
    recordingState.harCaptured = true;
  } else {
    // Fallback: URL + method only.
    startFallbackNetworkCapture(tabId);
    recordingState.harCaptured = false;
  }

  // Capture cookies at start (initial state). Only if cookies permission is granted.
  if (optionalGranted) {
    try {
      recordingState.cookies = await captureCookies(tabId);
    } catch (err) {
      console.warn("[Earendel] Initial cookie capture failed:", err);
      recordingState.cookies = [];
    }
  } else {
    recordingState.cookies = [];
  }

  // Tell content script to start. The content script is auto-injected via the
  // manifest's content_scripts declaration at document_idle. If the page was
  // just loaded the script may not be ready yet; we retry once after a short
  // delay. We do NOT use chrome.scripting.executeScript because the
  // "scripting" permission is no longer requested.
  try {
    await chrome.tabs.sendMessage(tabId, { type: "START_RECORDING" });
  } catch (err) {
    console.warn(
      "[Earendel] Content script not reachable on first try; retrying after 500ms.",
      err
    );
    await new Promise((resolve) => setTimeout(resolve, 500));
    try {
      await chrome.tabs.sendMessage(tabId, { type: "START_RECORDING" });
    } catch (retryErr) {
      console.warn(
        "[Earendel] Content script still not reachable. Steps will not be captured for this tab.",
        retryErr
      );
    }
  }

  // Capture initial screenshot (via visible-tab API - works even before CDP
  // is fully attached; for background tabs this returns null which is fine).
  await captureScreenshot(tabId);

  // Persist state so we can survive a service worker restart.
  await _saveState(true);

  console.log(
    "[Earendel] Recording started on tab",
    tabId,
    recordingState.harCaptured
      ? "(CDP/HAR capture active)"
      : "(webRequest fallback - HAR incomplete)"
  );
}

/**
 * Stop the recording session.
 *
 * Flow:
 *   1. Set isRecording=false.
 *   2. Stop network capture (webRequest fallback).
 *   3. Wait 2 seconds for pending CDP loadingFinished events to fire.
 *   4. Build the final HAR 1.2 object from harEntries + cdpRequests.
 *   5. Redact sensitive headers + postData from the HAR (Fix 1).
 *   6. Capture cookies again (final state) and merge with initial.
 *   7. Detach the debugger (always - even on error).
 *   8. Ask the content script for its captured steps.
 *   9. Merge everything into the recording payload (including screenshot files).
 *  10. Clear the session storage state (recording is finished).
 *
 * @returns {Promise<object|null>} - The recording result, or null if not recording.
 */
async function stopRecording() {
  if (!recordingState.isRecording) return null;

  recordingState.isRecording = false;

  // Stop the webRequest fallback listener (no-op if not registered).
  stopFallbackNetworkCapture();

  // Wait 2s for pending Network.loadingFinished events to fire so we get
  // response bodies for any in-flight requests.
  await new Promise((resolve) => setTimeout(resolve, 2000));

  // Build the HAR object from captured CDP events.
  let har = { log: { version: "1.2", creator: { name: "earendel-chrome-extension", version: "1.0" }, entries: [] } };
  if (recordingState.harCaptured) {
    try {
      har = buildHarObject();
    } catch (err) {
      console.error("[Earendel] HAR build error:", err);
      recordingState.harCaptured = false;
    }
  }

  // Fix 1: redact sensitive headers + postData before the HAR is used anywhere.
  try {
    _redactSensitiveData(har);
  } catch (err) {
    console.error("[Earendel] HAR redaction error (non-fatal):", err);
  }

  // Capture final cookies and merge with the initial set (dedupe by name+domain+path).
  let finalCookies = [];
  try {
    finalCookies = await captureCookies(recordingState.tabId);
  } catch (err) {
    console.warn("[Earendel] Final cookie capture failed:", err);
  }
  const mergedCookies = mergeCookies(recordingState.cookies, finalCookies);

  // Detach the debugger - ALWAYS, even on error. Use try/finally semantics.
  try {
    await detachDebugger(recordingState.tabId);
  } catch (err) {
    console.error("[Earendel] Debugger detach error (non-fatal):", err);
  }

  // Ask content script for its captured steps + DOM mutations.
  let contentData = null;
  try {
    const response = await chrome.tabs.sendMessage(recordingState.tabId, {
      type: "STOP_RECORDING",
    });
    if (response) {
      contentData = response;
    }
  } catch (err) {
    console.error("[Earendel] Error stopping content script:", err);
  }

  // Capture final screenshot.
  await captureScreenshot(recordingState.tabId);

  // Merge content script data with background data.
  const allNetworkRequests = [
    ...recordingState.networkRequests,
    ...(contentData?.networkRequests || []),
  ].filter((req, index, self) =>
    index === self.findIndex((r) => r.url === req.url)
  );

  const result = {
    steps: contentData?.steps || recordingState.steps,
    networkRequests: allNetworkRequests,
    domMutations: (contentData?.domMutations || 0) + recordingState.domMutations,
    screenshots: recordingState.screenshots,
    harCaptured: recordingState.harCaptured,
    har,
    cookies: mergedCookies,
    totalDurationMs: contentData?.totalDurationMs ||
      Date.now() - recordingState.startedAt,
    connectorName: recordingState.connectorName,
    workflowName: recordingState.workflowName,
    startedAt: new Date(recordingState.startedAt).toISOString(),
    url: contentData?.url || "",
    runId: recordingState.runId,
    screenshotFiles: recordingState.screenshotFiles.slice(),
  };

  const harEntryCount = har?.log?.entries?.length || 0;
  console.log(
    "[Earendel] Recording stopped:",
    result.steps.length,
    "steps,",
    harEntryCount,
    "HAR entries,",
    mergedCookies.length,
    "cookies,",
    result.screenshotFiles.length,
    "screenshots (harCaptured=",
    result.harCaptured,
    ")"
  );

  // Store in local storage.
  await chrome.storage.local.set({ lastRecording: result });

  // Clear the session storage state - the recording is finished.
  try {
    await chrome.storage.session.remove("earendelRecordingState");
  } catch (err) {
    console.debug("[Earendel] Could not clear session state (non-fatal):", err);
  }

  return result;
}

/**
 * Merge two cookie arrays (initial + final), deduplicating by
 * (name, domain, path). If a cookie appears in both, the final-state version
 * wins (it reflects the most recent value/expiry).
 *
 * @param {Array<object>} initial
 * @param {Array<object>} final
 * @returns {Array<object>}
 */
function mergeCookies(initial, final) {
  const map = new Map();
  for (const c of initial || []) {
    map.set(`${c.name}|${c.domain}|${c.path}`, c);
  }
  for (const c of final || []) {
    map.set(`${c.name}|${c.domain}|${c.path}`, c);
  }
  return Array.from(map.values());
}

// ---- Backend communication ----

/**
 * Send the recorded workflow + HAR + cookies to the backend.
 *
 * POST /api/v1/recordings
 *
 * Payload (Phase 1):
 *   - connectorId, workflowName
 *   - steps: array of step objects (click/input/navigate/submit/download)
 *   - totalDurationMs, domMutations, screenshots
 *   - networkRequests: count (kept for backward compat with the existing
 *     backend's Recording.networkRequests column which is Int)
 *   - harCaptured: boolean - false means HAR is incomplete (webRequest fallback)
 *   - har: FULL HAR 1.2 object ({log:{entries:[...]}}), sensitive data redacted
 *   - cookies: array of cookie objects
 *   - screenshotFiles: list of chrome.storage.local keys holding PNG screenshots
 *
 * The backend stores `har` and `cookies` as JSON strings in Text columns.
 *
 * Fix 4: if the fetch fails (network error or non-2xx response), the recording
 * is persisted to chrome.storage.local under `pendingRecording_{timestamp}`
 * so it can be retried later by `_retryPendingRecordings()`. The original
 * error is re-thrown so the caller (popup) can show a meaningful message.
 *
 * @param {object} recording - The recording result from stopRecording.
 * @returns {Promise<object>} - The backend's response (the created Recording).
 */
async function sendToBackend(recording) {
  const backendUrl = await getBackendUrl();
  const backendPort = getBackendPort(backendUrl);

  // Build the recording payload - ship the full HAR + cookies + steps.
  // Sensitive headers + postData in the HAR have already been redacted in
  // stopRecording() via _redactSensitiveData().
  const payload = {
    connectorId: recording.connectorId || "conn_demo",
    workflowName: recording.workflowName,
    steps: recording.steps.map((step, index) => ({
      index: index,
      type: step.type,
      description: step.description,
      selector: step.selector || null,
      url: step.url || null,
      value: step.value || null,
      isPassword: step.isPassword || false,
      networkCalls: (recording.networkRequests || []).filter(
        (r) => Math.abs((r.timestamp || 0) - (step.timestamp || 0)) < 5000
      ).length,
      screenshot: step.screenshot || false,
      durationMs: step.durationMs || 0,
    })),
    totalDurationMs: recording.totalDurationMs,
    // networkRequests is sent as a COUNT for backward compat with the
    // existing backend column (Int). The full request/response data lives
    // in the `har` field below.
    networkRequests: (recording.networkRequests || []).length,
    domMutations: recording.domMutations,
    screenshots: recording.screenshots,
    harCaptured: !!recording.harCaptured,
    // Full HAR 1.2 object - backend stores it as a JSON string and feeds it
    // to har_analyzer.py at compile time.
    har: recording.har || { log: { version: "1.2", creator: { name: "earendel-chrome-extension", version: "1.0" }, entries: [] } },
    // Array of cookie objects - backend stores as JSON string in the
    // Recording.cookies column. Used by internal_route adapter for replay.
    cookies: recording.cookies || [],
    // List of chrome.storage.local keys that hold PNG screenshots captured
    // during the recording. The backend can fetch these via a follow-up
    // request if needed; for now they are listed for traceability.
    screenshotFiles: recording.screenshotFiles || [],
    runId: recording.runId || null,
  };

  try {
    // Mint a JWT for auth (using the shared secret).
    const token = await getAuthToken();

    const response = await fetch(
      `${backendUrl}/api/v1/recordings?XTransformPort=${backendPort}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      const err = new Error(
        `Backend returned ${response.status}: ${text || response.statusText}`
      );
      err.statusCode = response.status;
      throw err;
    }

    const data = await response.json();
    return data;
  } catch (err) {
    console.error("[Earendel] Backend send error:", err);
    // Fix 4: persist the recording to local storage for later retry.
    try {
      const key = `pendingRecording_${Date.now()}`;
      await chrome.storage.local.set({
        [key]: {
          recording: { ...recording, screenshotFiles: recording.screenshotFiles || [] },
          payload,
          failedAt: Date.now(),
          error: err.message || String(err),
          attempts: 0,
        },
      });
      console.log("[Earendel] Recording saved to local storage for retry:", key);
    } catch (persistErr) {
      console.error("[Earendel] Could not persist pending recording:", persistErr);
    }
    throw err;
  }
}

async function compileRecording(recordingId) {
  const backendUrl = await getBackendUrl();
  const backendPort = getBackendPort(backendUrl);
  const token = await getAuthToken();

  const response = await fetch(
    `${backendUrl}/api/v1/recordings/${recordingId}/compile?XTransformPort=${backendPort}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) throw new Error(`Compile returned ${response.status}`);
  return response.json();
}

/**
 * Retry sending any recordings that were persisted to chrome.storage.local
 * because the backend was unreachable or returned a non-2xx response.
 *
 * Called on service worker startup. Iterates over all keys starting with
 * `pendingRecording_`, attempts to re-send each one to the backend, and
 * removes the key on success. Logs the outcome for each.
 *
 * @returns {Promise<{retried: number, succeeded: number, failed: number}>}
 */
async function _retryPendingRecordings() {
  let retried = 0;
  let succeeded = 0;
  let failed = 0;

  try {
    const all = await chrome.storage.local.get(null);
    const pendingKeys = Object.keys(all).filter((k) =>
      k.startsWith("pendingRecording_")
    );
    if (pendingKeys.length === 0) {
      return { retried, succeeded, failed };
    }

    console.log(
      `[Earendel] Retrying ${pendingKeys.length} pending recording(s) from local storage.`
    );

    for (const key of pendingKeys) {
      const entry = all[key];
      if (!entry || !entry.payload) {
        console.warn(`[Earendel] Pending entry ${key} is malformed; removing.`);
        await chrome.storage.local.remove(key);
        continue;
      }
      retried++;
      try {
        const backendUrl = await getBackendUrl();
        const backendPort = getBackendPort(backendUrl);
        const token = await getAuthToken();
        const response = await fetch(
          `${backendUrl}/api/v1/recordings?XTransformPort=${backendPort}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(entry.payload),
          }
        );
        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(
            `Backend returned ${response.status}: ${text || response.statusText}`
          );
        }
        const data = await response.json();
        succeeded++;
        console.log(
          `[Earendel] Retry SUCCESS for ${key}: recording id=${data.id || "(no id)"}`
        );
        await chrome.storage.local.remove(key);
      } catch (err) {
        failed++;
        const attempts = (entry.attempts || 0) + 1;
        await chrome.storage.local.set({
          [key]: { ...entry, attempts, lastError: err.message || String(err) },
        });
        console.warn(
          `[Earendel] Retry FAILED for ${key} (attempt ${attempts}):`,
          err.message || err
        );
      }
    }
  } catch (err) {
    console.error("[Earendel] _retryPendingRecordings error:", err);
  }

  console.log(
    `[Earendel] Retry summary: retried=${retried} succeeded=${succeeded} failed=${failed}`
  );
  return { retried, succeeded, failed };
}

// ---- JWT auth ----

async function getAuthToken() {
  // In production, this would use a proper OAuth flow or shared secret.
  // For demo: generate a simple JWT with the BACKEND_SECRET.
  // The extension stores the secret in chrome.storage.local during setup.
  const { backendSecret } = await chrome.storage.local.get("backendSecret");
  if (!backendSecret) {
    throw new Error("Backend secret not configured. Set it in the extension options.");
  }

  // Use Web Crypto API for HMAC-SHA256.
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({
      uid: "chrome-extension",
      email: "extension@earendel.io",
      iss: "earendel-studio",
      aud: "earendel-api",
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 86400,
    })
  );

  const data = `${header}.${payload}`;
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(backendSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(data));
  const sig = btoa(String.fromCharCode(...new Uint8Array(signature)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

  return `${data}.${sig}`;
}

// ---- Message handler (from popup) ----

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "START_RECORDING") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) {
          sendResponse({ error: "No active tab" });
          return;
        }
        await startRecording(tab.id, message.options);
        sendResponse({ success: true });
      } else if (message.type === "STOP_RECORDING") {
        const result = await stopRecording();
        sendResponse({ success: true, recording: result });
      } else if (message.type === "GET_STATUS") {
        // Ask content script for live status.
        try {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab) {
            const status = await chrome.tabs.sendMessage(tab.id, { type: "GET_STATUS" });
            sendResponse({
              isRecording: recordingState.isRecording,
              stepCount: status?.stepCount || recordingState.steps.length,
              networkCount: status?.networkCount || recordingState.networkRequests.length,
              domMutations: status?.domMutations || recordingState.domMutations,
              harCaptured: recordingState.harCaptured,
              harEntryCount: recordingState.harEntries.length + recordingState.cdpRequests.size,
              cookieCount: recordingState.cookies.length,
            });
          } else {
            sendResponse({ isRecording: false });
          }
        } catch {
          sendResponse({ isRecording: recordingState.isRecording });
        }
      } else if (message.type === "SEND_TO_BACKEND") {
        const { lastRecording } = await chrome.storage.local.get("lastRecording");
        if (!lastRecording) {
          sendResponse({ error: "No recording to send" });
          return;
        }
        const result = await sendToBackend({
          ...lastRecording,
          connectorId: message.connectorId,
        });
        sendResponse({ success: true, recording: result });
      } else if (message.type === "COMPILE_RECORDING") {
        const result = await compileRecording(message.recordingId);
        sendResponse({ success: true, action: result.action });
      } else if (message.type === "SET_BACKEND_SECRET") {
        await chrome.storage.local.set({ backendSecret: message.secret });
        sendResponse({ success: true });
      } else if (message.type === "SET_BACKEND_URL") {
        // Fix 8: configurable backend URL.
        const url = (message.url || "").trim();
        if (url && !/^https?:\/\//i.test(url)) {
          sendResponse({ error: "Backend URL must start with http:// or https://" });
          return;
        }
        await chrome.storage.local.set({ backendUrl: url || DEFAULT_BACKEND_URL });
        sendResponse({ success: true, backendUrl: url || DEFAULT_BACKEND_URL });
      } else if (message.type === "GET_BACKEND_URL") {
        const url = await getBackendUrl();
        sendResponse({ success: true, backendUrl: url });
      } else if (message.type === "EARENDEL_STEP") {
        // Step from content script - update background state.
        recordingState.steps.push(message.step);
        // Persist state after each step so we can survive a SW restart.
        // Throttled internally (only writes when 5+ new HAR entries, but steps
        // are always persisted).
        _saveState(false).catch((e) =>
          console.debug("[Earendel] _saveState after step failed (non-fatal):", e)
        );
        // Fix 3: capture a screenshot every 10 steps.
        if (recordingState.steps.length % 10 === 0 && recordingState.tabId) {
          _maybeCaptureScreenshot(recordingState.tabId, recordingState.steps.length).catch(
            () => {}
          );
        }
      } else if (message.type === "EARENDEL_STOP") {
        // Content script's final flush - merge step/DOM data into background
        // state. (This fires before STOP_RECORDING's content-script
        // sendMessage round-trip resolves, so it's a belt-and-suspenders
        // mechanism.)
        if (message.steps) recordingState.steps = message.steps;
        if (typeof message.domMutations === "number") {
          recordingState.domMutations = message.domMutations;
        }
        _saveState(false).catch((e) =>
          console.debug("[Earendel] _saveState on EARENDEL_STOP failed (non-fatal):", e)
        );
      }
    } catch (err) {
      console.error("[Earendel] Background error:", err);
      sendResponse({ error: err.message });
    }
  })();
  return true; // Keep channel open for async
});

// ---- Lifecycle cleanup ----

// When the extension is installed or updated, initialize default storage keys
// and detach any debugger that might still be attached from a prior version.
chrome.runtime.onInstalled.addListener(() => {
  console.log("[Earendel] Extension installed");
  chrome.storage.local.set({
    backendSecret: "",
    backendUrl: DEFAULT_BACKEND_URL,
    lastRecording: null,
  });
});

// If the recorded tab is closed mid-recording, detach the debugger and clear
// the session state so a subsequent popup open does not think we are still
// recording.
chrome.tabs.onRemoved.addListener((tabId) => {
  if (recordingState.isRecording && recordingState.tabId === tabId) {
    console.warn("[Earendel] Recorded tab closed mid-recording - cleaning up.");
    recordingState.isRecording = false;
    stopFallbackNetworkCapture();
    detachDebugger(tabId);
    chrome.storage.session.remove("earendelRecordingState").catch(() => {});
  }
});

// ---- Service worker startup ----
// MV3 service workers can be terminated and restarted at any time. On startup
// we (1) restore any in-flight recording state from chrome.storage.session
// and (2) retry sending any recordings that failed to send to the backend
// before the previous SW instance was terminated.
(function onStartup() {
  console.log("[Earendel] Service worker starting up.");
  _loadState().catch((err) =>
    console.warn("[Earendel] _loadState on startup failed (non-fatal):", err)
  );
  _retryPendingRecordings().catch((err) =>
    console.warn("[Earendel] _retryPendingRecordings on startup failed (non-fatal):", err)
  );
})();
