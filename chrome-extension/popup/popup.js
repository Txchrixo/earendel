/**
 * Earendel Recorder - Popup UI logic
 *
 * Handles the popup interactions: start/stop recording, live stats,
 * send to backend, compile via LLM. Also manages:
 *   - Fix 7: consent notice (shown until the user accepts it once)
 *   - Fix 8: configurable backend URL (stored in chrome.storage.local)
 */

(function () {
  "use strict";

  // ---- DOM elements ----
  const startBtn = document.getElementById("start-btn");
  const stopBtn = document.getElementById("stop-btn");
  const discardBtn = document.getElementById("discard-btn");
  const compileBtn = document.getElementById("compile-btn");
  const statusBadge = document.getElementById("status-badge");
  const statusText = document.getElementById("status-text");
  const statsSection = document.getElementById("stats-section");
  const stepsSection = document.getElementById("steps-section");
  const stepsPreview = document.getElementById("steps-preview");
  const postRecording = document.getElementById("post-recording");
  const messageArea = document.getElementById("message-area");
  const setupLink = document.getElementById("setup-link");
  const setupPanel = document.getElementById("setup-panel");
  const saveSecretBtn = document.getElementById("save-secret-btn");

  // Fix 7: consent notice elements
  const consentOverlay = document.getElementById("consent-overlay");
  const consentAcceptBtn = document.getElementById("consent-accept-btn");
  const revokeConsentLink = document.getElementById("revoke-consent-link");

  // Fix 8: backend URL elements
  const backendUrlInput = document.getElementById("backend-url");
  const saveUrlBtn = document.getElementById("save-url-btn");

  let statsInterval = null;
  let lastRecording = null;
  let consentAccepted = false;

  // ---- Helpers ----

  function sendMessage(type, data = {}) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type, ...data }, resolve);
    });
  }

  function showMessage(text, isError = false) {
    messageArea.innerHTML = "";
    const el = document.createElement("div");
    el.className = isError ? "error" : "success";
    el.textContent = text;
    messageArea.appendChild(el);
    setTimeout(() => el.remove(), 5000);
  }

  function setRecordingUI(isRecording) {
    if (isRecording) {
      startBtn.style.display = "none";
      stopBtn.style.display = "block";
      statsSection.style.display = "block";
      stepsSection.style.display = "block";
      postRecording.style.display = "none";
      statusBadge.className = "status-badge status-recording";
      statusBadge.querySelector(".dot").className = "dot dot-recording";
      statusText.textContent = "Recording";
    } else {
      startBtn.style.display = "block";
      stopBtn.style.display = "none";
      statusBadge.className = "status-badge status-idle";
      statusBadge.querySelector(".dot").className = "dot dot-idle";
      statusText.textContent = "Idle";
    }
  }

  function updateStats(status) {
    document.getElementById("stat-steps").textContent = status.stepCount || 0;
    document.getElementById("stat-network").textContent = status.networkCount || 0;
    document.getElementById("stat-dom").textContent = status.domMutations || 0;
    document.getElementById("stat-screenshots").textContent = status.screenshots || 0;
  }

  function renderSteps(steps) {
    stepsPreview.innerHTML = "";
    for (const step of steps.slice(-20)) {
      // Show last 20
      const el = document.createElement("div");
      el.className = "step-item";
      const typeEl = document.createElement("span");
      typeEl.className = `step-type step-type-${step.type}`;
      typeEl.textContent = step.type;
      const desc = document.createElement("span");
      desc.textContent = step.description || step.type;
      el.appendChild(typeEl);
      el.appendChild(desc);
      stepsPreview.appendChild(el);
    }
    stepsPreview.scrollTop = stepsPreview.scrollHeight;
  }

  // ---- Fix 7: consent notice ----

  /**
   * Show the consent overlay if the user has not yet accepted it. The consent
   * state is stored in chrome.storage.local under the key "recordingConsent"
   * and persists across popup opens (and browser restarts).
   */
  function showConsentIfNeeded() {
    if (!consentAccepted) {
      consentOverlay.style.display = "flex";
      // Disable the start button while the consent overlay is visible so the
      // user cannot start a recording without first accepting.
      startBtn.disabled = true;
    } else {
      consentOverlay.style.display = "none";
      startBtn.disabled = false;
    }
  }

  consentAcceptBtn.addEventListener("click", async () => {
    try {
      await chrome.storage.local.set({
        recordingConsent: { accepted: true, acceptedAt: Date.now() },
      });
      consentAccepted = true;
      showConsentIfNeeded();
      showMessage("Consent recorded. You can start recording now.");
    } catch (err) {
      showMessage(`Could not save consent: ${err.message}`, true);
    }
  });

  // Revoke consent: clears the stored flag so the overlay re-appears on the
  // next popup open. Useful if the user wants to revisit the privacy notice.
  revokeConsentLink.addEventListener("click", async () => {
    try {
      await chrome.storage.local.remove("recordingConsent");
      consentAccepted = false;
      showConsentIfNeeded();
      setupPanel.classList.remove("visible");
      showMessage("Consent revoked. Please re-accept to continue recording.");
    } catch (err) {
      showMessage(`Could not revoke consent: ${err.message}`, true);
    }
  });

  // ---- Fix 8: backend URL configuration ----

  saveUrlBtn.addEventListener("click", async () => {
    const url = (backendUrlInput.value || "").trim();
    if (url && !/^https?:\/\//i.test(url)) {
      showMessage("Backend URL must start with http:// or https://", true);
      return;
    }
    const response = await sendMessage("SET_BACKEND_URL", { url });
    if (response?.error) {
      showMessage(response.error, true);
      return;
    }
    showMessage(`Backend URL saved: ${response.backendUrl || url}`);
  });

  // ---- Event handlers ----

  startBtn.addEventListener("click", async () => {
    // Fix 7: block recording until consent is accepted.
    if (!consentAccepted) {
      showConsentIfNeeded();
      showMessage("Please accept the consent notice first.", true);
      return;
    }

    const connectorName = document.getElementById("connector-name").value;
    const workflowName = document.getElementById("workflow-name").value;

    const response = await sendMessage("START_RECORDING", {
      options: { connectorName, workflowName },
    });

    if (response?.error) {
      showMessage(response.error, true);
      return;
    }

    setRecordingUI(true);

    // Start polling for stats
    statsInterval = setInterval(async () => {
      const status = await sendMessage("GET_STATUS");
      if (status) {
        updateStats(status);
        // Get steps from storage
        const { lastRecording: rec } = await chrome.storage.local.get("lastRecording");
        if (rec?.steps) renderSteps(rec.steps);
      }
    }, 1000);
  });

  stopBtn.addEventListener("click", async () => {
    if (statsInterval) clearInterval(statsInterval);

    const response = await sendMessage("STOP_RECORDING");
    if (response?.error) {
      showMessage(response.error, true);
      return;
    }

    setRecordingUI(false);

    if (response.recording) {
      lastRecording = response.recording;
      updateStats({
        stepCount: response.recording.steps.length,
        networkCount: response.recording.networkRequests.length,
        domMutations: response.recording.domMutations,
        screenshots: response.recording.screenshots,
      });
      renderSteps(response.recording.steps);
      postRecording.style.display = "block";
      showMessage(`Recording captured: ${response.recording.steps.length} steps`);
    }
  });

  discardBtn.addEventListener("click", () => {
    lastRecording = null;
    postRecording.style.display = "none";
    statsSection.style.display = "none";
    stepsSection.style.display = "none";
    showMessage("Recording discarded");
  });

  compileBtn.addEventListener("click", async () => {
    compileBtn.disabled = true;
    compileBtn.textContent = "Sending to backend...";

    try {
      // Send recording to backend
      const connectorId = "conn_demo"; // In production, user would select this
      const sendResponse = await sendMessage("SEND_TO_BACKEND", { connectorId });

      if (sendResponse?.error) {
        // Fix 4: the recording was persisted to local storage for retry, so
        // inform the user that it will be re-sent automatically later.
        showMessage(
          `Error: ${sendResponse.error}. Recording saved for automatic retry.`,
          true
        );
        compileBtn.disabled = false;
        compileBtn.textContent = "Compile to Action";
        return;
      }

      const recordingId = sendResponse.recording?.id;
      if (!recordingId) {
        showMessage("Recording saved but no ID returned", true);
        compileBtn.disabled = false;
        compileBtn.textContent = "Compile to Action";
        return;
      }

      // Compile via LLM
      compileBtn.textContent = "Compiling via LLM...";
      const compileResponse = await sendMessage("COMPILE_RECORDING", { recordingId });

      if (compileResponse?.error) {
        showMessage(`Compile error: ${compileResponse.error}`, true);
      } else if (compileResponse?.action) {
        showMessage(
          `Compiled: ${compileResponse.action.name}(${compileResponse.action.contract?.inputs?.map((i) => i.name).join(", ") || ""})`
        );
        postRecording.style.display = "none";
      }
    } catch (err) {
      showMessage(`Error: ${err.message}`, true);
    }

    compileBtn.disabled = false;
    compileBtn.textContent = "Compile to Action";
  });

  // Setup panel toggle
  setupLink.addEventListener("click", () => {
    setupPanel.classList.toggle("visible");
  });

  saveSecretBtn.addEventListener("click", async () => {
    const secret = document.getElementById("backend-secret").value;
    if (!secret) {
      showMessage("Enter the backend secret", true);
      return;
    }
    await sendMessage("SET_BACKEND_SECRET", { secret });
    showMessage("Backend secret saved");
    setupPanel.classList.remove("visible");
  });

  // ---- Initial load ----
  (async () => {
    // Fix 7: load consent state.
    try {
      const { recordingConsent } = await chrome.storage.local.get("recordingConsent");
      consentAccepted = !!(recordingConsent && recordingConsent.accepted);
    } catch {
      consentAccepted = false;
    }
    showConsentIfNeeded();

    // Fix 8: load the configured backend URL into the input field.
    try {
      const urlResp = await sendMessage("GET_BACKEND_URL");
      if (urlResp?.backendUrl) {
        backendUrlInput.value = urlResp.backendUrl;
      }
    } catch {
      // Fall back to the default value already in the HTML.
    }

    // Check initial recording status on popup open.
    const status = await sendMessage("GET_STATUS");
    if (status?.isRecording) {
      setRecordingUI(true);
      updateStats(status);
      statsInterval = setInterval(async () => {
        const s = await sendMessage("GET_STATUS");
        if (s) updateStats(s);
      }, 1000);
    }
  })();
})();
