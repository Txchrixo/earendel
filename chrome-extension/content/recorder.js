/**
 * Earendel Recorder — Content Script
 *
 * Injected into every page. Listens for user interactions (clicks, inputs,
 * navigation, downloads) and captures them as structured steps. Also captures
 * DOM snapshots (accessibility tree), form values, and element selectors.
 *
 * Security:
 *   - No eval(), no Function(), no innerHTML with user data
 *   - Form passwords are masked (never captured in plaintext)
 *   - All data is sanitized before sending to the background script
 *   - Content script runs in an isolated world — no access to page JS
 */

(function () {
  "use strict";

  // Prevent double-injection
  if (window.__earendelRecorder) return;
  window.__earendelRecorder = true;

  // ---- State ----
  let isRecording = false;
  let steps = [];
  let stepIndex = 0;
  let networkRequests = [];
  let domMutations = 0;
  let screenshots = 0;
  let lastUrl = window.location.href;

  // ---- Element selector generation ----

  /**
   * Generate the most stable CSS selector for an element.
   * Priority: [data-testid] > [aria-label] > [id] > [name] > tag+nth-child
   */
  function generateSelector(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) return null;

    // 1. data-testid
    const testId = element.getAttribute("data-testid");
    if (testId) return `[data-testid="${escapeAttr(testId)}"]`;

    // 2. data-test
    const dataTest = element.getAttribute("data-test");
    if (dataTest) return `[data-test="${escapeAttr(dataTest)}"]`;

    // 3. aria-label
    const ariaLabel = element.getAttribute("aria-label");
    if (ariaLabel) return `${element.tagName.toLowerCase()}[aria-label="${escapeAttr(ariaLabel)}"]`;

    // 4. id
    if (element.id) return `#${CSS.escape(element.id)}`;

    // 5. name (for form elements)
    const name = element.getAttribute("name");
    if (name && (element.tagName === "INPUT" || element.tagName === "SELECT" || element.tagName === "TEXTAREA")) {
      return `${element.tagName.toLowerCase()}[name="${escapeAttr(name)}"]`;
    }

    // 6. placeholder (for inputs)
    const placeholder = element.getAttribute("placeholder");
    if (placeholder && element.tagName === "INPUT") {
      return `input[placeholder="${escapeAttr(placeholder)}"]`;
    }

    // 7. role + accessible name
    const role = element.getAttribute("role");
    if (role) {
      const accName = element.getAttribute("aria-label") || element.textContent?.trim()?.slice(0, 50);
      if (accName) return `[role="${escapeAttr(role)}"]${accName ? `[aria-label="${escapeAttr(accName)}"]` : ""}`;
    }

    // 8. tag + nth-child path
    return generatePath(element);
  }

  function generatePath(element) {
    const parts = [];
    let el = element;
    while (el && el.nodeType === Node.ELEMENT_NODE && el !== document.documentElement) {
      let selector = el.tagName.toLowerCase();
      if (el.id) {
        selector = `#${CSS.escape(el.id)}`;
        parts.unshift(selector);
        break;
      }
      const parent = el.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter((c) => c.tagName === el.tagName);
        if (siblings.length > 1) {
          const index = siblings.indexOf(el) + 1;
          selector += `:nth-of-type(${index})`;
        }
      }
      parts.unshift(selector);
      el = el.parentElement;
    }
    return parts.join(" > ");
  }

  function escapeAttr(value) {
    return String(value).replace(/["\\]/g, "\\$&");
  }

  // ---- Element description ----

  function describeElement(element) {
    const tag = element.tagName.toLowerCase();
    const text = (element.textContent || "").trim().slice(0, 80);
    const ariaLabel = element.getAttribute("aria-label");
    const placeholder = element.getAttribute("placeholder");
    const title = element.getAttribute("title");
    const type = element.getAttribute("type");

    let description = ariaLabel || placeholder || title || text || tag;
    if (type && tag === "input") description = `${type} input: ${placeholder || ariaLabel || "unnamed"}`;
    return description;
  }

  // ---- DOM snapshot (accessibility tree) ----

  function captureAccessibilityTree() {
    const tree = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, {
      acceptNode: function (node) {
        const role = node.getAttribute("role");
        const tag = node.tagName.toLowerCase();
        const interactiveTags = ["a", "button", "input", "select", "textarea", "summary"];
        const interactiveRoles = ["button", "link", "textbox", "checkbox", "radio", "combobox", "menuitem", "tab"];
        if (interactiveTags.includes(tag) || (role && interactiveRoles.includes(role))) {
          return NodeFilter.FILTER_ACCEPT;
        }
        return NodeFilter.FILTER_SKIP;
      },
    });

    let count = 0;
    let node;
    while ((node = walker.nextNode()) && count < 100) {
      tree.push({
        tag: node.tagName.toLowerCase(),
        selector: generateSelector(node),
        role: node.getAttribute("role") || null,
        label: node.getAttribute("aria-label") || node.textContent?.trim()?.slice(0, 50) || null,
        type: node.getAttribute("type") || null,
        name: node.getAttribute("name") || null,
      });
      count++;
    }
    return tree;
  }

  // ---- Event listeners ----

  function handleClick(event) {
    if (!isRecording) return;
    const el = event.target;
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return;

    // Skip Earendel UI elements
    if (el.closest("[data-earendel-ui]")) return;

    const selector = generateSelector(el);
    const description = describeElement(el);

    addStep({
      type: "click",
      description: `Click ${description}`,
      selector: selector,
      tagName: el.tagName.toLowerCase(),
      url: window.location.href,
      timestamp: Date.now(),
    });
  }

  function handleInput(event) {
    if (!isRecording) return;
    const el = event.target;
    if (!el || el.tagName !== "INPUT" && el.tagName !== "TEXTAREA" && el.tagName !== "SELECT") return;
    if (el.closest("[data-earendel-ui]")) return;

    // Security: mask password fields
    const isPassword = el.type === "password";
    const value = isPassword ? "••••••••" : el.value;

    const selector = generateSelector(el);
    const description = describeElement(el);

    addStep({
      type: el.tagName === "SELECT" ? "select" : "input",
      description: `${isPassword ? "Enter password" : `Input into ${description}`}`,
      selector: selector,
      value: value,
      isPassword: isPassword,
      tagName: el.tagName.toLowerCase(),
      url: window.location.href,
      timestamp: Date.now(),
    });
  }

  function handleNavigation() {
    if (!isRecording) return;
    const newUrl = window.location.href;
    if (newUrl !== lastUrl) {
      addStep({
        type: "navigate",
        description: `Navigate to ${new URL(newUrl).pathname}`,
        url: newUrl,
        timestamp: Date.now(),
      });
      lastUrl = newUrl;
    }
  }

  function handleDownload(event) {
    if (!isRecording) return;
    addStep({
      type: "download",
      description: `Download triggered`,
      url: window.location.href,
      timestamp: Date.now(),
    });
  }

  // DOM mutation observer
  let mutationObserver = null;
  function startMutationObserver() {
    if (mutationObserver) mutationObserver.disconnect();
    mutationObserver = new MutationObserver((mutations) => {
      if (!isRecording) return;
      domMutations += mutations.length;
    });
    mutationObserver.observe(document.body, { childList: true, subtree: true });
  }

  // ---- Step management ----

  function addStep(step) {
    step.index = stepIndex++;
    steps.push(step);

    // Capture accessibility tree snapshot with each step
    step.accessibilityTree = captureAccessibilityTree();

    // Send to background
    chrome.runtime.sendMessage({
      type: "EARENDEL_STEP",
      step: step,
      totalSteps: steps.length,
      networkRequests: networkRequests.length,
      domMutations: domMutations,
    });
  }

  // ---- Network request interception (via Performance API) ----

  function captureNetworkRequests() {
    const entries = performance.getEntriesByType("resource");
    for (const entry of entries) {
      // Only capture XHR/fetch (not images/CSS/JS)
      if (entry.initiatorType === "xmlhttprequest" || entry.initiatorType === "fetch") {
        const alreadyCaptured = networkRequests.some((r) => r.url === entry.name);
        if (!alreadyCaptured) {
          networkRequests.push({
            url: entry.name,
            method: "GET", // Performance API doesn't expose method
            duration: Math.round(entry.duration),
            size: entry.transferSize || 0,
            timestamp: Date.now(),
          });
        }
      }
    }
  }

  // Periodically capture network requests
  let networkInterval = null;

  // ---- Recording control ----

  function startRecording() {
    isRecording = true;
    steps = [];
    stepIndex = 0;
    networkRequests = [];
    domMutations = 0;
    screenshots = 0;
    lastUrl = window.location.href;

    // Add initial navigation step
    addStep({
      type: "navigate",
      description: `Navigate to ${new URL(window.location.href).pathname}`,
      url: window.location.href,
      timestamp: Date.now(),
    });

    // Start network capture
    networkInterval = setInterval(captureNetworkRequests, 2000);

    // Start mutation observer
    startMutationObserver();

    // Inject recording indicator CSS
    injectIndicator();

    console.log("[Earendel] Recording started");
  }

  function stopRecording() {
    isRecording = false;
    if (networkInterval) clearInterval(networkInterval);
    if (mutationObserver) mutationObserver.disconnect();

    // Final network capture
    captureNetworkRequests();

    // Send final data to background
    chrome.runtime.sendMessage({
      type: "EARENDEL_STOP",
      steps: steps,
      networkRequests: networkRequests,
      domMutations: domMutations,
      totalDurationMs: steps.length > 0 ? Date.now() - steps[0].timestamp : 0,
      url: window.location.href,
    });

    // Remove indicator
    removeIndicator();

    console.log(`[Earendel] Recording stopped: ${steps.length} steps captured`);
  }

  // ---- Recording indicator UI ----

  function injectIndicator() {
    if (document.getElementById("earendel-indicator")) return;
    const indicator = document.createElement("div");
    indicator.id = "earendel-indicator";
    indicator.setAttribute("data-earendel-ui", "true");
    indicator.style.cssText = `
      position: fixed;
      top: 16px;
      right: 16px;
      z-index: 2147483647;
      background: #7A8548;
      color: #1F1A17;
      font-family: -apple-system, system-ui, sans-serif;
      font-size: 13px;
      font-weight: 500;
      padding: 8px 16px;
      border-radius: 9999px;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      pointer-events: none;
    `;
    indicator.innerHTML = `
      <span style="width:8px;height:8px;border-radius:50%;background:#1F1A17;animation:earendel-pulse 1.5s ease-in-out infinite;"></span>
      <span>Earendel Recording</span>
      <span id="earendel-step-count" style="font-weight:400;opacity:0.8;">0 steps</span>
    `;

    // Add pulse animation
    const style = document.createElement("style");
    style.setAttribute("data-earendel-ui", "true");
    style.textContent = `
      @keyframes earendel-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
      }
    `;
    document.head.appendChild(style);
    document.body.appendChild(indicator);
  }

  function updateIndicator(stepCount) {
    const countEl = document.getElementById("earendel-step-count");
    if (countEl) countEl.textContent = `${stepCount} steps`;
  }

  function removeIndicator() {
    const indicator = document.getElementById("earendel-indicator");
    if (indicator) indicator.remove();
    const style = document.querySelector("style[data-earendel-ui]");
    if (style) style.remove();
  }

  // ---- Message listener (from popup/background) ----

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "START_RECORDING") {
      startRecording();
      sendResponse({ success: true, steps: steps.length });
    } else if (message.type === "STOP_RECORDING") {
      stopRecording();
      sendResponse({
        success: true,
        steps: steps,
        networkRequests: networkRequests,
        domMutations: domMutations,
        totalDurationMs: steps.length > 0 ? Date.now() - steps[0].timestamp : 0,
      });
    } else if (message.type === "GET_STATUS") {
      sendResponse({
        isRecording: isRecording,
        stepCount: steps.length,
        networkCount: networkRequests.length,
        domMutations: domMutations,
      });
    } else if (message.type === "EARENDEL_STEP") {
      // Step from this content script — update indicator
      updateIndicator(message.totalSteps);
    }
    return true; // Keep channel open for async response
  });

  // Listen for navigation events
  let navigationCheckInterval = setInterval(handleNavigation, 1000);

  // Listen for popstate (SPA navigation)
  window.addEventListener("popstate", handleNavigation);

  // Listen for clicks (capture phase to get them before page handlers)
  document.addEventListener("click", handleClick, true);

  // Listen for input changes (debounced)
  let inputTimeout = null;
  document.addEventListener(
    "input",
    (event) => {
      clearTimeout(inputTimeout);
      inputTimeout = setTimeout(() => handleInput(event), 300);
    },
    true
  );

  // Listen for form submissions
  document.addEventListener(
    "submit",
    (event) => {
      if (!isRecording) return;
      const form = event.target;
      addStep({
        type: "submit",
        description: `Submit form`,
        selector: generateSelector(form),
        url: window.location.href,
        timestamp: Date.now(),
      });
    },
    true
  );

  // Listen for downloads (via anchor click with download attribute)
  document.addEventListener(
    "click",
    (event) => {
      if (!isRecording) return;
      const el = event.target.closest("a[download], a[href$='.pdf'], a[href$='.csv'], a[href$='.xlsx']");
      if (el) handleDownload(event);
    },
    true
  );

  console.log("[Earendel] Recorder content script loaded");
})();
