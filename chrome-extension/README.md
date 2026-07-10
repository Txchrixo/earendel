# Earendel Chrome Extension - Real Workflow Recorder

## Installation

1. Open `chrome://extensions` in Chrome/Edge
2. Enable "Developer mode" (top-right toggle)
3. Click "Load unpacked"
4. Select the `chrome-extension/` folder from this project
5. The Earendel icon appears in your toolbar

## Setup

1. Click the Earendel extension icon
2. Click "⚙ Backend settings"
3. Enter the `BACKEND_SECRET` from your `.env` file
4. Click "Save"

## Recording a workflow

1. Navigate to the website you want to record (e.g. `https://supplier-portal.acme.com`)
2. Click the Earendel extension icon
3. Enter the connector name and workflow name
4. Click "Start Recording"
5. Perform the workflow as a human would (login, search, download, etc.)
6. Click "Stop" when done
7. Review the captured steps
8. Click "Compile to Action" to send to the backend + compile via LLM

## What it captures

| Signal | Method | Security |
|---|---|---|
| Clicks | `document.addEventListener('click', handler, true)` | Element selector + description only |
| Inputs | `document.addEventListener('input', handler, true)` | Passwords masked as `••••••••` |
| Navigation | `popstate` + URL polling | URL only |
| Form submissions | `document.addEventListener('submit', handler, true)` | Form selector only |
| Downloads | Click on `a[download]`, `a[href$='.pdf']` etc. | URL only |
| Network requests | `chrome.webRequest.onBeforeRequest` | URL + method only (no bodies) |
| DOM mutations | `MutationObserver` | Count only |
| Screenshots | `chrome.tabs.captureVisibleTab` | PNG dataURL |
| Accessibility tree | `document.createTreeWalker` | Element role/label/tag only |

## Security

- **Manifest V3** (latest Chrome extension standard)
- **CSP**: `script-src 'self'; object-src 'self'` - no inline scripts, no eval
- **Content script isolation**: runs in isolated world, no access to page JS
- **Password masking**: password fields are never captured in plaintext
- **No request/response bodies**: network capture stores only URL + method
- **JWT auth**: extension mints its own JWT with the shared BACKEND_SECRET
- **Local storage only**: recording data stays in `chrome.storage.local` until sent
- **No remote code**: all code is bundled in the extension, nothing loaded from CDN

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Chrome Extension                                │
│                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Popup   │←→│  Background  │←→│  Content  │ │
│  │  UI      │  │  Service     │  │  Script   │ │
│  │          │  │  Worker      │  │           │ │
│  └──────────┘  └──────┬───────┘  └───────────┘ │
│                       │                          │
│                       │ JWT auth                 │
└───────────────────────┼──────────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  FastAPI Backend │
              │  (port 8001)    │
              │                 │
              │  POST /recordings       │
              │  POST /recordings/:id/compile │
              └─────────────────┘
```

## Files

```
chrome-extension/
├── manifest.json              # Manifest V3 config
├── content/
│   └── recorder.js            # Content script (injected into pages)
├── background/
│   └── service-worker.js      # Background service worker (network capture, screenshots, auth)
├── popup/
│   ├── popup.html             # Extension popup UI
│   └── popup.js               # Popup logic
└── icons/                     # Extension icons (16/48/128px)
```
