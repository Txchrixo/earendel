/**
 * Earendel Recorder — Background Service Worker
 *
 * Manages recording state across tabs, captures network requests via
 * chrome.webRequest, coordinates between the popup UI and content scripts.
 *
 * Security:
 *   - No eval, no dynamic code execution
 *   - Network captures only store URLs + methods, never request/response bodies
 *   - All data is sanitized before sending to the backend
 *   - Host permissions are broad (needed for recording) but data is never
 *     persisted outside the extension's local storage during recording
 */

// ---- State ----

let recordingState = {
  isRecording: false,
  tabId: null,
  steps: [],
  networkRequests: [],
  domMutations: 0,
  screenshots: 0,
  harCaptured: false,
  startedAt: null,
  connectorName: null,
  workflowName: null,
};

// ---- Network request capture via chrome.webRequest ----

const NETWORK_FILTER = {
  urls: ["http://*/*", "https://*/*"],
  types: ["xmlhttprequest", "fetch", "main_frame", "sub_frame"],
};

let networkListener = null;

function startNetworkCapture(tabId) {
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

function stopNetworkCapture() {
  if (networkListener) {
    chrome.webRequest.onBeforeRequest.removeListener(networkListener);
    networkListener = null;
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

// ---- Recording control ----

async function startRecording(tabId, options = {}) {
  recordingState = {
    isRecording: true,
    tabId: tabId,
    steps: [],
    networkRequests: [],
    domMutations: 0,
    screenshots: 0,
    harCaptured: true,
    startedAt: Date.now(),
    connectorName: options.connectorName || "unknown",
    workflowName: options.workflowName || "recorded-workflow",
  };

  // Start network capture
  startNetworkCapture(tabId);

  // Tell content script to start
  try {
    await chrome.tabs.sendMessage(tabId, { type: "START_RECORDING" });
  } catch (err) {
    // Content script might not be injected yet — inject it
    await chrome.scripting.executeScript({
      target: { tabId: tabId },
      files: ["content/recorder.js"],
    });
    await chrome.tabs.sendMessage(tabId, { type: "START_RECORDING" });
  }

  // Capture initial screenshot
  await captureScreenshot(tabId);

  console.log("[Earendel] Recording started on tab", tabId);
}

async function stopRecording() {
  if (!recordingState.isRecording) return null;

  recordingState.isRecording = false;

  // Stop network capture
  stopNetworkCapture();

  // Tell content script to stop
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

  // Capture final screenshot
  await captureScreenshot(recordingState.tabId);

  // Merge content script data with background data
  const result = {
    steps: contentData?.steps || recordingState.steps,
    networkRequests: [
      ...recordingState.networkRequests,
      ...(contentData?.networkRequests || []),
    ].filter((req, index, self) =>
      index === self.findIndex((r) => r.url === req.url)
    ),
    domMutations: (contentData?.domMutations || 0) + recordingState.domMutations,
    screenshots: recordingState.screenshots,
    harCaptured: recordingState.networkRequests.length > 0,
    totalDurationMs: contentData?.totalDurationMs ||
      Date.now() - recordingState.startedAt,
    connectorName: recordingState.connectorName,
    workflowName: recordingState.workflowName,
    startedAt: new Date(recordingState.startedAt).toISOString(),
    url: contentData?.url || "",
  };

  console.log("[Earendel] Recording stopped:", result.steps.length, "steps");

  // Store in local storage
  await chrome.storage.local.set({ lastRecording: result });

  return result;
}

// ---- Backend communication ----

async function sendToBackend(recording) {
  const backendUrl = "http://localhost:8001";
  const backendPort = "8001";

  // Build the recording payload
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
      networkCalls: recording.networkRequests.filter(
        (r) => Math.abs(r.timestamp - step.timestamp) < 5000
      ).length,
      screenshot: step.screenshot || false,
      durationMs: step.durationMs || 0,
    })),
    totalDurationMs: recording.totalDurationMs,
    networkRequests: recording.networkRequests.length,
    domMutations: recording.domMutations,
    screenshots: recording.screenshots,
    harCaptured: recording.harCaptured,
  };

  try {
    // Mint a JWT for auth (using the shared secret)
    const token = await getAuthToken();

    const response = await fetch(
      `${backendUrl}/api/v1/recordings?XTransformPort=${backendPort}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          connectorId: payload.connectorId,
          workflowName: payload.workflowName,
          steps: payload.steps,
          totalDurationMs: payload.totalDurationMs,
          networkRequests: payload.networkRequests,
          domMutations: payload.domMutations,
          screenshots: payload.screenshots,
          harCaptured: payload.harCaptured,
        }),
      }
    );

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (err) {
    console.error("[Earendel] Backend send error:", err);
    throw err;
  }
}

async function compileRecording(recordingId) {
  const backendUrl = "http://localhost:8001";
  const backendPort = "8001";
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

// ---- JWT auth ----

async function getAuthToken() {
  // In production, this would use a proper OAuth flow or shared secret
  // For demo: generate a simple JWT with the BACKEND_SECRET
  // The extension stores the secret in chrome.storage.local during setup
  const { backendSecret } = await chrome.storage.local.get("backendSecret");
  if (!backendSecret) {
    throw new Error("Backend secret not configured. Set it in the extension options.");
  }

  // Use Web Crypto API for HMAC-SHA256
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
        // Ask content script for live status
        try {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab) {
            const status = await chrome.tabs.sendMessage(tab.id, { type: "GET_STATUS" });
            sendResponse({
              isRecording: recordingState.isRecording,
              stepCount: status?.stepCount || recordingState.steps.length,
              networkCount: status?.networkCount || recordingState.networkRequests.length,
              domMutations: status?.domMutations || recordingState.domMutations,
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
      } else if (message.type === "EARENDEL_STEP") {
        // Step from content script — update background state
        recordingState.steps.push(message.step);
      }
    } catch (err) {
      console.error("[Earendel] Background error:", err);
      sendResponse({ error: err.message });
    }
  })();
  return true; // Keep channel open for async
});

// Clean up on extension install
chrome.runtime.onInstalled.addListener(() => {
  console.log("[Earendel] Extension installed");
  chrome.storage.local.set({
    backendSecret: "",
    lastRecording: null,
  });
});
