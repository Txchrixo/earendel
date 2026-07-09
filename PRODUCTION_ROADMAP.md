# Earendel — Production-Readiness Roadmap

> **Document type:** End-to-end plan to take Earendel from "well-architected demo with overclaimed features" to "honestly production-ready system that delivers on its promises."
>
> **Methodology:** This plan is grounded in (a) a brutally honest code audit (see §0) and (b) a literature review of **~136 research papers** across network discovery, self-healing automation, web-agent reliability, contract testing, and multi-tenant registry design (see §References).
>
> **Honesty principle:** Every phase states what is currently REAL, PARTIAL, SIMULATED, or MISLEADING, and what the phase makes it. No phase is marked "done" until the claim is verifiably true against real external systems.

---

## Table of Contents

0. Honest Audit — Where We Actually Are
1. Phase 0 — Stop Lying (fix misleading claims)
2. Phase 1 — Real Network Capture (Option B moat)
3. Phase 2 — Real Repair Flywheel with Embeddings (Option A moat)
4. Phase 3 — Real Browser Automation
5. Phase 4 — Real BU Integration (or remove it)
6. Phase 5 — Real Vision Adapter
7. Phase 6 — Real Canary Scheduler
8. Phase 7 — Evaluation Harness (prove the 10×/10×/500× claims)
9. Phase 8 — Multi-Tenant Registry (Option C moat)
10. Phase 9 — Production Infrastructure
11. Phase 10 — Real Connector Auth (OAuth2)
12. Cross-Phase Dependencies (DAG)
13. Reference Paper Library (136 papers, organized)

---

## §0. Honest Audit — Where We Actually Are

A line-by-line audit of the code (not the worklog claims) yields this classification:

| # | Claim | Status | Reality |
|---|-------|--------|---------|
| 1 | Network Discovery (Option B) | **PARTIAL** | Real analyzer + real replay logic; only synthetic HAR ever fed in; Chrome extension captures URLs but not bodies; `Recording` has no `har` field; `compile` endpoint calls `_synthesize_demo_har()` instead of using real captured data |
| 2 | Repair Flywheel ("RAG") | **MISLEADING** | KB storage + 3-tier ladder real; "RAG" is plain SQL equality matching on `(domain, widget, intention)` — no embeddings, no vector similarity |
| 3 | Browser Adapter + stealth | **PARTIAL** | Real Playwright + real 7 evasions; but workflows target non-existent domains (`supplier-portal.acme.com` doesn't resolve) → always falls back to simulation |
| 4 | BU Browser Adapter | **SIMULATED** | Real HTTP plumbing; math parser cannot solve real BU word-problem challenges (verified: BU returns obfuscated text, parser raises `ValueError`); `BrowserUseKey` table empty — never provisioned |
| 5 | Vision Adapter | **SIMULATED** | Real z-ai vision CLI exists; never receives a screenshot (`EARENDEL_SCREENSHOT_PATH` never set) → always falls back to deterministic stub |
| 6 | LLM integration | **REAL** | z-ai CLI installed and verified; both repair_proposer and schema_compiler actually call it |
| 7 | Postconditions | **REAL** | Real type + named-postcondition checks; properly wired to orchestrator fallback |
| 8 | Canary Monitoring ("every 15 min") | **MISLEADING** | No scheduler exists; manual endpoint only; dashboard chart injects synthetic baseline data |
| 9 | MCP Server | **REAL** | Real JSON-RPC 2.0; tools/list + tools/call wired to backend |
| 10 | Versioning + Rollback | **REAL** | Real semver bump + contract snapshot + rollback |
| 11 | Frontend | **REAL** | All 15 view files fetch real data via real API calls |
| 12 | "10×/10×/500×" claims | **MISLEADING** | No benchmark/eval harness; numbers are asserted; 120ms baseline is the simulation duration, not a measured replay time |

**Tally: 5 REAL, 3 PARTIAL, 2 SIMULATED, 4 MISLEADING.**

**The uncomfortable truth:** Earendel is currently a well-architected simulation with real plumbing. The orchestrator, contracts, versioning, MCP, and frontend are genuinely production-grade. The three moats (network discovery, repair flywheel, BU stealth) are overstated. The "10×/10×/500×" claims are marketing, not measurements.

This roadmap fixes every one of these gaps.

---

## Phase 0 — Stop Lying (Week 1)

**Goal:** Align every claim with reality. No feature is advertised that isn't real.

### 0.1 Fix the README

- Replace "10× faster (120 ms vs 1.5 s)" with "designed for sub-second replay; benchmark pending (see Phase 7)".
- Replace "95.92% precision (APISENSOR)" citation — that's APISENSOR's number on their data, not Earendel's. Rephrase: "APISENSOR demonstrates 95.92% precision on HAR→endpoint discovery; Earendel implements a similar approach but has not yet been benchmarked at scale."
- Replace "BU browser adapter (optional)" section with "BU browser adapter (experimental — provisioning not yet working against the real BU API; see Phase 4)".
- Replace "Canaries every 15 minutes" with "Manual canary endpoint; automatic scheduler planned (see Phase 6)".
- Replace "RAG-style lookup" with "cross-client pattern-matched KB lookup (SQL-based; embedding-based retrieval planned — see Phase 2)".

### 0.2 Fix the docstrings

- `backend/app/infrastructure/prisma_repositories.py:1109` — change "RAG-style lookup" to "categorical SQL lookup with confidence/success ranking".
- `backend/app/core/discovery/har_analyzer.py` — add a note that the analyzer is real but the recording pipeline currently only feeds synthetic HAR.
- `backend/app/adapters/bu_browser_adapter.py` — add a module-level docstring note: "PROVISIONING IS CURRENTLY BROKEN against the real BU API — the challenge format returns obfuscated word problems, not arithmetic. See Phase 4."

### 0.3 Fix the frontend landing page

- `src/components/earendel/landing-page.tsx:35-40` — the STATS array claims "95% route-discovery precision", "82-96% token reduction", "30-40% RPA budget lost". Either source these or mark them as "industry statistics, not Earendel measurements".

### 0.4 Add an "Honest Status" section to the README

A table like §0 above, kept in sync with reality. This builds trust.

**Exit criteria:** Every public-facing claim (README, landing page, docstrings) is either (a) true and verifiable, or (b) explicitly marked as planned/experimental with a phase reference.

**Papers grounding this phase:** None — this is an honesty phase, not a research phase.

---

## Phase 1 — Real Network Capture (Option B moat) (Weeks 2-3)

**Goal:** When a user records a workflow in the Chrome extension, Earendel captures real HAR (with request/response bodies), discovers real endpoints, and replays them.

**Current state:** The HAR analyzer (`har_analyzer.py`) is real and well-engineered, but it has only ever been fed synthetic data from `demo_har.py`. The Chrome extension captures URLs but not bodies. The `Recording` entity has no `har` field. The compile endpoint ignores any real HAR and calls `_synthesize_demo_har()`.

### 1.1 Upgrade the Chrome extension to capture full HAR

**File:** `chrome-extension/background/service-worker.js`

Currently (lines 42-63), the extension only uses `chrome.webRequest.onBeforeRequest` to capture URLs + methods. This is insufficient — we need request bodies, response bodies, headers, status codes, and timings.

**Implementation:**
- Use the **Chrome DevTools Protocol (CDP)** via `chrome.debugger` API to capture `Network.requestWillBeSent`, `Network.responseReceived`, `Network.loadingFinished` events. This gives full request/response bodies.
- Alternatively, use `chrome.webRequest.onBeforeRequest` with `requestBody` parsing + `fetch()` interception via a content script that wraps `window.fetch` and `XMLHttpRequest`.
- Serialize captured data as **standard HAR 1.2 format** (`{log: {entries: [{request: {...}, response: {...}, timings: {...}}]}}`).
- Send the HAR to the backend via the existing recording-save endpoint.

**Academic grounding:**
- **APISENSOR** (arXiv:2603.23852, 2026) — the key reference; their two-stage clustering + denoising on real traffic is the algorithm Earendel's analyzer approximates.
- **Black Widow** (IEEE S&P 2021) — blackbox data-driven web scanning from observed HTTP traffic; their state-machine reconstruction complements HAR analysis.
- **Carving UI Tests to Generate API Tests** (ICSE 2023) — almost identical pipeline (UI → HAR → API spec + replayable tests); direct template.
- **Discoverer** (USENIX Security 2007) — seminal protocol-reverse-engineering from network traces.

### 1.2 Add a `har` field to the Recording entity

**Files:** `prisma/schema.prisma`, `backend/app/core/domain/entities.py`, `backend/app/infrastructure/prisma_repositories.py`

Add `har String @default("{}")` to the `Recording` model (stored as JSON string). Update the SQLAlchemy `RecordingModel` and the Pydantic `Recording` entity. Add a `har: dict` field to the entity with a JSON parser.

### 1.3 Wire the compile endpoint to use real HAR

**File:** `backend/app/modules/recordings/router.py:71-72`

Change:
```python
if rec.harCaptured:
    har = _synthesize_demo_har(action.name)
```
To:
```python
har = rec.har if rec.har and rec.har != "{}" else _synthesize_demo_har(action.name)
if rec.har and rec.har != "{}":
    # Real HAR captured — analyze it
    candidates = analyze_har(rec.har, action.name, rec.connectorId)
    await store_discovered_endpoints(candidates, action.name, rec.connectorId)
```

Keep `_synthesize_demo_har` as a fallback for demo/test recordings that have no real HAR.

### 1.4 Add a cookie/session acquisition flow

**Problem:** Even with real endpoints discovered, the `internal_route` adapter needs session cookies to replay them. Currently, cookies are expected in env vars (`ACME_SESSION_COOKIE` etc.) that are never set.

**Implementation:**
- During recording, the Chrome extension captures cookies for the target domain via `chrome.cookies.getAll({domain: targetDomain})`.
- Store the cookies (encrypted) in the `Connector.credentialVaultKey` field (already exists in the schema).
- The `internal_route` adapter reads cookies from the vault instead of env vars.
- Add a cookie-refresh flow: when a replay returns 401/403, mark the endpoint as "auth-stale" and trigger a re-record prompt.

**Academic grounding:**
- **RESTler** (ICSE 2019) — stateful REST API fuzzing with producer/consumer dependency inference; their sequence-replay logic handles auth state.
- **RESTTESTGEN** (ICST 2020) — resource-constraint extraction (e.g., an `id` returned by POST is required by DELETE); directly applicable to replay correctness.
- **MINES** (arXiv:2512.06906, 2025) — schema-level invariant inference; the natural next step after endpoint discovery.

### 1.5 Stale endpoint detection (already partial — harden it)

**Current state:** `internal_route_adapter.py` marks endpoints stale on HTTP 404/410. Good.

**Hardening:**
- Also mark stale on schema mismatch (response keys don't match `responseShape`).
- Add a re-discovery flow: when an endpoint is marked stale, automatically trigger a re-record prompt + re-analyze.
- Add a "endpoint health" canary that periodically pings discovered endpoints to detect drift before a real execution fails.

**Academic grounding:**
- **Differential Regression Testing for REST APIs** (ISSTA 2020) — compare two API versions on the same inputs to surface regressions; template for Earendel's stale detection.
- **Metamorphic Testing of RESTful Web APIs** (TSE 2017) — six abstract metamorphic relations (idempotency, commutativity) serve as oracles for replay correctness without a ground-truth spec.
- **WebNorm** (ASE 2024) — infer normative behavioral invariants from traffic; turns captured HAR into an anomaly-detection layer.

### 1.6 Tests

- Unit test: feed a real HAR (from a real recording of a real portal — e.g., Stripe test mode, JSONPlaceholder) through `analyze_har()` and assert the discovered endpoints match the real API.
- Integration test: record a workflow → compile → assert `DiscoveredEndpoint` rows are populated from real HAR, not from `_synthesize_demo_har`.
- E2E test: run an action through the orchestrator → assert `internal_route` adapter succeeds against a real endpoint with real cookies.

**Exit criteria:** A user can record a workflow on a real portal (e.g., Stripe test dashboard), and Earendel discovers and replays the real internal API endpoint — not a simulation.

---

## Phase 2 — Real Repair Flywheel with Embeddings (Option A moat) (Weeks 3-4)

**Goal:** The repair KB uses real embedding-based retrieval (not SQL equality matching) so semantically-similar failures match across clients.

**Current state:** `knowledge_base.py:query_kb()` calls `repair_kb_search()` which is a SQL `WHERE targetDomain == ? AND widgetType == ? AND intention == ?` query. This is categorical matching, not semantic retrieval. Calling it "RAG" is misleading.

### 2.1 Add an embedding store

**Implementation:**
- Add a `RepairEmbedding` model: `{patternKey, embedding (vector), text_hash}`.
- Use `sentence-transformers` (e.g., `all-MiniLM-L6-v2`) to embed the failure signature: `(action_name + " " + error_message + " " + failed_selector + " " + page_text_snippet)`.
- Store the embedding (768-dim float vector) in SQLite as a JSON string (or migrate to PostgreSQL with `pgvector` for production).
- Add a `query_by_embedding(failure_text, top_k=5)` function that computes cosine similarity against all stored embeddings.

**Academic grounding:**
- **RAP-Gen** (retrieval-augmented patch generation) — the canonical RAG-for-repair pattern.
- **ReAPR** — retrieval-augmented automated program repair.
- **ReCode** — fine-grained retrieval for code repair.
- **RAG-for-code survey** — maps the design space.

### 2.2 Replace `query_kb()` with embedding-based retrieval

**File:** `backend/app/core/repair/knowledge_base.py`

Change `query_kb()`:
1. Embed the failure signature.
2. Query the top-5 most similar KB entries by cosine similarity (threshold: 0.85).
3. Among those, apply the existing `_combined_score` ranking (confidence × log1p(success) × 1/(1+failure)).
4. Return the best if combined_score > threshold.

Keep the SQL categorical matching as a secondary signal (boost entries that match on `target_domain`).

### 2.3 Add page-text context to failures

**Problem:** Currently, the repair proposer only sees `(action_name, error_message, failed_selector)`. Two failures with the same selector on different pages are treated as the same pattern — they're not.

**Implementation:**
- When a browser adapter fails, capture the page's visible text (via `page.inner_text('body')`) and the DOM HTML around the failed selector.
- Pass this context to the repair proposer and the KB.
- Embed `(action_name + error_message + failed_selector + page_text_snippet)` for richer semantic matching.

**Academic grounding:**
- **Semter** (FSE 2023) — intent abstraction for cross-client transfer; the "intention" is what makes repairs transferable, not the selector.
- **Similo** (TOSEM 2023) — element-matching features (text, DOM context, attributes) for locator repair; directly reusable as embedding inputs.
- **UITESTFIX** (ASE 2023) — LLM-based test repair with page context.

### 2.4 Honest relabeling

- Rename "RAG-style lookup" → "embedding-based retrieval with cross-client KB" in all docstrings and the README.
- Only use the term "RAG" if an LLM is actually used in the retrieval step (e.g., the LLM rewrites the query before embedding). If so, implement that step.

### 2.5 Tests

- Embed 10 real failure signatures from 10 different portals.
- Assert that a new failure on a similar (but not identical) portal retrieves the right repair.
- Assert that failures on completely different portals do NOT match (precision test).

**Exit criteria:** A failure at Client B on `button#export-pdf` retrieves a repair stored from Client A's failure on `a[aria-label='Download']` — because the embeddings capture semantic similarity, not exact selector match.

---

## Phase 3 — Real Browser Automation (Weeks 4-5)

**Goal:** The browser adapter launches real Playwright against real portals and succeeds.

**Current state:** Real Playwright + real stealth evasions, but `_WORKFLOW_REGISTRY` targets non-existent domains (`supplier-portal.acme.com` doesn't resolve). Every browser execution falls back to simulation.

### 3.1 Compile workflows from real recordings (not hardcoded)

**File:** `backend/app/adapters/browser_adapter.py`

Currently, `_WORKFLOW_REGISTRY` is a hardcoded dict mapping action names to step sequences. This is a demo artifact.

**Implementation:**
- Change `BrowserAdapter.execute()` to read the workflow from the action's `Recording.steps` (which are captured by the Chrome extension).
- Each recorded step becomes a Playwright action: `navigate`, `click`, `fill`, `wait`, `screenshot`, `download`.
- Keep `_WORKFLOW_REGISTRY` as a fallback for the 6 seeded demo actions.

### 3.2 Add real test portals

**Problem:** Every seeded workflow points at a fake domain. We need at least one real portal to test against.

**Implementation:**
- Add a `trackShipment` workflow that points at a real carrier's tracking page (e.g., Maersk's public tracking at `https://www.maersk.com/tracking` — no login required).
- Add a `downloadInvoice` workflow that points at Stripe's test-mode dashboard (login with test credentials).
- Add a `checkClaimStatus` workflow that points at a public claims-status demo (or build a small mock portal with Playwright's `route()` interception).
- Verify each workflow actually succeeds end-to-end against the real portal.

### 3.3 Screenshot capture + propagation

**Problem:** The browser adapter captures screenshots to `/tmp/earendel-screenshots/`, but the Vision adapter never receives them (Phase 5).

**Implementation:**
- Store screenshots as base64 in the `ExecutionContext` (or a shared screenshot store keyed by `run_id`).
- The orchestrator passes the screenshot list to the Vision adapter when it falls back.

### 3.4 Proxy + stealth hardening

**Current state:** 7 stealth evasions are real. Proxy config via env is real.

**Hardening:**
- Add CAPTCHA detection (if page contains `iframe[src*='captcha']` or `#cf-challenge`, escalate to BU adapter or human review).
- Add bot-detection evasion for Cloudflare/Datadome (these require more than JS evasions — residential proxies + fingerprint rotation).
- Document honestly: "stealth evasions handle basic webdriver detection; advanced bot protection (Cloudflare Turnstile, Datadome) requires the BU adapter or human escalation."

**Academic grounding:**
- **Browser Fingerprinting: A Survey** (ACM TWEB 2020) — the fingerprinting surface Earendel must defend against.
- **Hiding in the Crowd** (USENIX Security 2018) — fingerprint entropy measurement.
- **Taming the Shape Shifter** (DIMVA 2020) — anti-fingerprinting browser detection; the cat-and-mouse baseline.
- **Halligan** (USENIX Security 2025) — VLM-based CAPTCHA solver; "CAPTCHA is a solved sub-problem."
- **Building Browser Agents** (arXiv:2511.19477, 2025) — architecture of cloud browser-agent platforms.

### 3.5 Tests

- E2E test: run `trackShipment` against the real Maersk tracking page → assert the browser adapter succeeds and returns real tracking data.
- E2E test: run `downloadInvoice` against Stripe test mode → assert the browser adapter succeeds and downloads a real PDF.

**Exit criteria:** At least 3 seeded workflows succeed against real portals (not fake domains) via the real Playwright path.

---

## Phase 4 — Real BU Integration (or remove it) (Week 5)

**Goal:** Either the BU adapter actually provisions a key and runs a real task, or it's removed from the advertised 6-adapter chain.

**Current state:** The math parser cannot solve the real BU challenge (verified: BU returns obfuscated word problems like `I@f SeVeN| wOrKeRs CoMpLe!Te! A jOb...`, not arithmetic). `BrowserUseKey` table is empty — provisioning has never succeeded.

### 4.1 Option A: Fix the challenge solver with the LLM

**Implementation:**
- The BU challenge is a word problem with obfuscated text. First, clean the text (strip non-alphanumeric noise). Then, use the LLM (z-ai, already installed and working) to extract the arithmetic and solve it.
- Example: `I@f SeVeN| wOrKeRs CoMpLe!Te! A jOb [ In ? EiGhT|eEn DaYs...` → LLM extracts "If 7 workers complete a job in 18 days but 5 quit after day 16, how many days to finish?" → LLM solves: 7 workers × 18 days = 126 worker-days total. After 16 days, 7 × 16 = 112 worker-days done. Remaining: 126 - 112 = 14 worker-days. 2 workers remaining. 14 / 2 = 7 more days. Total: 16 + 7 = 23 days. Answer: `"23.00"`.
- Replace `_solve_math_challenge()` with `_solve_challenge_via_llm(challenge_text)` that calls `llm.complete()` with a prompt like: "Solve this word problem. Reply with only the numeric answer to 2 decimal places. Problem: {cleaned_text}".

### 4.2 Option B: Remove BU from the default chain

If the BU API is unstable or the challenge format keeps changing, honestly remove `bu_browser` from the default fallback chain. Keep the adapter code but mark it `experimental`. The chain becomes 5 adapters: `api → internal_route → browser → vision → human`.

### 4.3 Verify end-to-end

- Call `POST /api/v1/bu/provision` → assert a real `bu_...` API key is stored in `BrowserUseKey`.
- Run an action with `bu_browser` in its `executionMethods` → assert the BU adapter creates a real session, runs a real task, and returns real output.
- If BU's free tier is rate-limited, document it and add a quota check.

### 4.4 Honest marketing

- If BU works: update the README to say "BU adapter is production-verified against api.browser-use.com".
- If BU doesn't work: update the README to say "BU adapter is experimental; the local browser adapter + stealth is the recommended path for most use cases".

**Exit criteria:** Either (a) `BrowserUseKey` has a real key and a real task has been executed via BU Cloud, or (b) BU is removed from the advertised chain and marked experimental.

---

## Phase 5 — Real Vision Adapter (Week 5)

**Goal:** The vision adapter actually receives screenshots and calls the VLM.

**Current state:** The VLM CLI (`z-ai vision`) is installed and works. But `EARENDEL_SCREENSHOT_PATH` is never set, so `_call_vlm()` always returns `None` and falls back to simulation.

### 5.1 Plumb screenshots into the Vision adapter

**File:** `backend/app/adapters/vision_adapter.py`

**Implementation:**
- Add a `screenshots: list[str]` field to `ExecutionContext` (the base adapter context).
- The orchestrator sets this field with the screenshots captured by the browser adapter before calling the vision adapter.
- `VisionAdapter.execute()` reads `ctx.screenshots` (file paths or base64 strings) and passes them to `_call_vlm()`.
- `_call_vlm()` calls `z-ai vision --image <path> --prompt "<analyze this page and extract: {fields}>"`.

### 5.2 VLM prompt engineering

The VLM needs a structured prompt to extract the action's output fields from the screenshot:
```
You are analyzing a web page screenshot. The user wanted to {action.description}.
Extract the following fields from the page:
- invoiceNumber (string): the invoice number
- pdfUrl (url): the download URL for the invoice PDF
- amount (number): the total amount
- status (string): the payment status
Reply as JSON. If a field is not visible, set it to null.
```

### 5.3 Tests

- Capture a real screenshot of a real portal (e.g., Stripe test dashboard invoice page).
- Run the vision adapter → assert it returns real extracted data (not simulation).

**Exit criteria:** When the browser adapter fails and the orchestrator falls back to vision, the vision adapter receives the browser's screenshots and returns VLM-extracted data.

---

## Phase 6 — Real Canary Scheduler (Week 6)

**Goal:** Canaries actually run every 15 minutes for every `testing`/`published` action.

**Current state:** No scheduler exists. The dashboard chart injects synthetic baseline data to fake continuous activity.

### 6.1 Add APScheduler

**File:** `backend/app/main.py`

**Implementation:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(
        run_all_canaries,
        "interval",
        minutes=15,
        id="canary-runner",
        replace_existing=True,
    )
    scheduler.start()

@app.on_event("shutdown")
async def stop_scheduler():
    scheduler.shutdown(wait=False)
```

### 6.2 Implement `run_all_canaries()`

```python
async def run_all_canaries():
    actions = await action_list(status="published") + await action_list(status="testing")
    for action in actions:
        try:
            execution = await orchestrator.run(action, action.canary_inputs, Caller.canary, risk_approved=True)
            await execution_put(execution)
            if execution.status != "success":
                # Auto-trigger repair proposer
                await propose_repair(action, execution)
        except Exception as e:
            logger.error(f"Canary failed for {action.name}: {e}")
```

### 6.3 Remove synthetic baseline data

**File:** `backend/app/modules/monitoring/timeseries_service.py:46-65`

Remove the `baseline_total = 4 + (seed % 6)` and `baseline_success_rate = 0.78 + (seed % 18) / 100` injection. The chart should show real execution data only — even if that means empty hours.

### 6.4 Tests

- Start the backend → wait 15 minutes → assert canary executions appear in the DB.
- Or: manually trigger `run_all_canaries()` → assert every `published`/`testing` action gets a canary execution.

**Exit criteria:** The monitoring dashboard shows real canary executions every 15 minutes, with no synthetic data injection.

---

## Phase 7 — Evaluation Harness (prove the 10×/10×/500× claims) (Weeks 6-8)

**Goal:** Build a benchmark that measures Earendel's latency, success rate, and cost against a Browser Use baseline, and publish the methodology + results.

**Current state:** No benchmark exists. The "10×/10×/500×" numbers are asserted, not measured. The 120ms baseline is the simulation duration.

### 7.1 Build a benchmark suite

**Implementation:**
- Record 10-20 real workflows across real portals:
  - Stripe test mode: download invoice, list customers, create payment link
  - JSONPlaceholder: get post, list users, create post
  - GitHub API: list repos, get issue, create issue
  - A real supplier portal (with permission)
  - A real carrier tracking page
- For each workflow, run it 100× through Earendel (via the orchestrator) and 100× through a Browser Use baseline (via their Cloud API).
- Measure: latency (p50, p95, p99), success rate, cost (LLM tokens × price).

### 7.2 Compare against baselines

**Baselines:**
1. **Earendel full chain** (api → internal_route → browser → bu_browser → vision → human)
2. **Earendel API-only** (api adapter only — measures the "compiled" path)
3. **Browser Use Cloud** (LLM-at-every-step)
4. **Raw Playwright** (no LLM, hardcoded selectors — measures the "brittle" baseline)

### 7.3 Publish the methodology

- A `benchmarks/` directory with the workflow definitions, runner scripts, and results.
- A `BENCHMARKS.md` document with the methodology, results table, and caveats.
- Update the README's "10×/10×/500×" claims with actual measured numbers (or remove the claims if the measurements don't support them).

**Academic grounding:**
- **WebArena** (ICLR 2024) — the canonical web-agent benchmark; Earendel's eval should follow its methodology (task-success rate, partial credit).
- **WebArena Verified** (OpenReview 2025) — shows prior reported rates are inflated 1.4-5.2×; Earendel's eval must avoid this trap.
- **WAREX** (arXiv:2510.03285, 2025) — reliability re-evaluation under perturbation; Earendel should perturb portals (change selectors) and measure repair time.
- **OSWorld-MCP** (arXiv:2510.24563, 2025) — shows MCP tools lift success from 8.3% → 20.4%; Earendel should measure the MCP-native path vs click-based.
- **Beyond Browsing: API-Based Web Agents** (ACL Findings 2025) — empirical proof that hybrid (API + browsing) > browsing-only by 24%; Earendel should measure its hybrid chain.

### 7.4 Honest reporting

- If Earendel is 5× faster (not 10×), say 5×.
- If Earendel is 3× more reliable (not 10×), say 3×.
- If the cost saving is 100× (not 500×) because of LLM-at-compile-time, say 100×.
- Publish the raw data so others can verify.

**Exit criteria:** The README's performance claims cite a real benchmark with a real methodology, and the numbers match the measurements.

---

## Phase 8 — Multi-Tenant Registry (Option C moat) (Weeks 8-10)

**Goal:** A shared registry where actions are published once and consumed by all tenants, with per-tenant credentials and metered billing.

**Current state:** Publishing produces an MCP manifest, but there's no real multi-tenant registry. Each tenant has their own actions; there's no sharing.

### 8.1 Multi-tenant data model

**Implementation:**
- Add a `Tenant` model: `{id, name, slug, plan, createdAt}`.
- Add `tenantId` to `Connector`, `TypedAction`, `Recording`, `Execution`, `DiscoveredEndpoint`, `RepairKnowledge`.
- `RepairKnowledge` is **shared across tenants** (that's the flywheel). All other models are tenant-scoped.
- Add a `PublishedAction` model: `{actionId, tenantId, publishedAt, version, visibility (public/private), price_per_call}`. This is the registry entry.

### 8.2 Action discovery + consumption

**Implementation:**
- `GET /api/v1/registry/actions?q=downloadInvoice` — search the public registry (across all tenants).
- `POST /api/v1/registry/actions/{id}/subscribe` — a tenant subscribes to another tenant's published action.
- When a tenant runs a subscribed action, the orchestrator uses the subscriber's credentials (from their vault) but the publisher's action definition.
- Metering: every call increments `PublishedAction.call_count` and records a `UsageEvent` for billing.

### 8.3 Credential isolation

**Implementation:**
- Each tenant's credentials are stored in an encrypted vault keyed by `tenantId + connectorId`.
- The orchestrator never sees plaintext credentials — it passes a `vault_key` to the adapter, which decrypts at the last moment.
- Use a KMS (AWS KMS, GCP KMS, or a local equivalent for dev) for encryption.

**Academic grounding:**
- **A First Look at Security and Privacy Risks in the RapidAPI Ecosystem** (ACM FSE/ISSTA 2024) — the only empirical study of a real multi-tenant API marketplace's failure modes; Earendel must defend against the same vectors (key handling, action provenance, tenant isolation).
- **Multi-Tenant Architecture Design in Cloud-Native Applications** (2024) — isolation patterns (silo, bridge, pool).
- **WSO2 API Marketplace white paper** — provider/consumer roles, billing, SLAs.
- **AWS multi-tenant throttling** — per-tenant rate limiting and quota enforcement.
- **Open Banking APIs** — the most mature real-world multi-tenant API marketplace at national scale; governance lessons.

### 8.4 Pricing + billing

**Implementation:**
- Per-call pricing: `PublishedAction.price_per_call` (in cents).
- Free tier: 100 calls/month per tenant.
- Stripe integration for billing.
- Usage dashboard per tenant.

### 8.5 Tests

- Tenant A publishes `downloadInvoice`. Tenant B subscribes. Tenant B runs it with their own credentials → assert it works.
- Assert Tenant B cannot see Tenant A's credentials.
- Assert the `RepairKnowledge` flywheel: Tenant A's repair is applied to Tenant B's failure.

**Exit criteria:** Two tenants can share a published action, each using their own credentials, and the repair flywheel works across them.

---

## Phase 9 — Production Infrastructure (Weeks 10-11)

**Goal:** Earendel runs on PostgreSQL with proper secrets management, CI/CD, and observability.

### 9.1 Migrate SQLite → PostgreSQL

- Change `prisma/schema.prisma` provider to `postgresql`.
- Use `pgvector` for the embedding store (Phase 2).
- Update `DATABASE_URL` in production env.
- Run `prisma migrate deploy`.

### 9.2 Secrets management

- Move `BACKEND_SECRET`, `NEXTAUTH_SECRET`, BU API keys, session cookies out of `.env` into a real secrets manager (AWS Secrets Manager, Doppler, or Vault).
- The backend fetches secrets at startup, not from env files.

### 9.3 CI/CD

- GitHub Actions: on push → run `bun run lint` + `npx vitest run` + `python3 -m pytest tests/`.
- On merge to main → deploy to staging.
- On tag → deploy to production.

### 9.4 Observability

- Structured logging (JSON) with `structlog`.
- OpenTelemetry traces for every execution (span per adapter).
- Prometheus metrics: `earendel_executions_total{adapter, status}`, `earendel_execution_duration_ms`, `earendel_repair_kb_hits_total`.
- Grafana dashboard.

### 9.5 Deployment

- Docker Compose for dev (already exists via `start_services.py`).
- Kubernetes for production: Next.js deployment, FastAPI deployment, MCP server deployment, execution-stream deployment, PostgreSQL StatefulSet, Redis (for session cache).
- Or: Vercel (Next.js) + Railway/Fly.io (FastAPI + mini-services) + Neon (PostgreSQL).

**Exit criteria:** Earendel runs on PostgreSQL with CI/CD, secrets management, and observability — deployable to a real cloud.

---

## Phase 10 — Real Connector Auth (OAuth2) (Week 11)

**Goal:** Connectors authenticate via OAuth2 (not session cookies in env vars).

**Current state:** Connectors expect session cookies in env vars (`ACME_SESSION_COOKIE`). This is fine for MVP but doesn't scale — cookies expire, users can't refresh them, and it's not auditable.

### 10.1 OAuth2 flow

**Implementation:**
- Add an OAuth2 callback endpoint: `GET /api/v1/connectors/{id}/oauth/callback?code=...`.
- For each connector type (Stripe, Maersk, BlueCross, etc.), define an OAuth2 config: `{authorize_url, token_url, client_id, client_secret, scopes}`.
- The frontend's connector-detail view has a "Connect with OAuth" button that redirects to the authorize URL.
- On callback, exchange the code for an access token + refresh token, store them encrypted in the vault.
- The `internal_route` adapter uses the access token (refreshing as needed).

### 10.2 Token refresh

- Add a background job that refreshes tokens 1 hour before expiry.
- If refresh fails, mark the connector as `auth_expired` and notify the user.

### 10.3 Supported providers

- Stripe (OAuth2 for Connect)
- GitHub (OAuth2 app)
- Google (OAuth2 for Gmail/Drive/etc.)
- Custom OAuth2 for arbitrary providers (config-driven)

**Exit criteria:** A user can connect a Stripe account via OAuth2, and Earendel uses the access token to call Stripe's API — no session cookies in env vars.

---

## §12. Cross-Phase Dependencies (DAG)

```
Phase 0 (Stop Lying) ──── no dependencies, do first
    │
    ├──▶ Phase 1 (Real Network Capture) ──── unblocks the Option B moat
    │       │
    │       └──▶ Phase 7 (Eval Harness) ──── needs real workflows to benchmark
    │
    ├──▶ Phase 2 (Real Repair Flywheel) ──── unblocks the Option A moat
    │       │
    │       └──▶ Phase 8 (Multi-Tenant Registry) ──── needs the flywheel to work cross-tenant
    │
    ├──▶ Phase 3 (Real Browser Automation) ──── needs real recordings (Phase 1)
    │       │
    │       ├──▶ Phase 5 (Real Vision Adapter) ──── needs browser screenshots
    │       │
    │       └──▶ Phase 4 (Real BU Integration) ──── alternative to local browser
    │
    ├──▶ Phase 6 (Real Canary Scheduler) ──── independent
    │
    ├──▶ Phase 9 (Production Infra) ──── independent, but unblocks Phase 8 + 10
    │
    └──▶ Phase 10 (OAuth2 Connectors) ──── needs Phase 9 (secrets management)
```

**Critical path:** Phase 0 → Phase 1 → Phase 3 → Phase 7. This is the path to "honestly production-ready with proven claims."

**Parallel tracks:** Phase 2, Phase 6, Phase 9 can run in parallel with the critical path.

**Long pole:** Phase 8 (Multi-Tenant Registry) is the most ambitious and requires Phases 1, 2, 9 to be done first.

---

## §13. Reference Paper Library

### A. Network Discovery / API Inference from Traffic (25 papers)

**Key references:**
1. **APISENSOR** (arXiv:2603.23852, 2026) — 95.92% precision HAR→endpoint discovery. The core reference.
2. **Internal APIs Are All You Need** (arXiv:2604.00694, 2026) — independently argues the Earendel thesis.
3. **Carving UI Tests to Generate API Tests** (ICSE 2023) — closest published pipeline to Earendel's.
4. **Black Widow** (IEEE S&P 2021) — blackbox data-driven discovery from traffic.
5. **RESTler** (ICSE 2019) — canonical replay engine.
6. **MOREST** (ICSE 2022) — property-graph modeling of endpoints.
7. **RESTTESTGEN** (ICST 2020) — resource-constraint extraction.
8. **EvoMaster** (ICST 2018) — search-based REST fuzzing.
9. **Schemathesis** (arXiv:2112.10328, 2021) — schema-aware fuzzing.
10. **Respector** (ICSE 2024) — static API spec generation.
11. **LlamaRestTest** (arXiv:2501.08598, 2025) — SLM-based REST testing.
12. **MINER** (USENIX Security 2023) — hybrid data-driven fuzzing.
13. **SpecWeaver** (ACM FSE 2026) — multi-layer routing spec inference.
14. **MINES** (arXiv:2512.06906, 2025) — schema-level invariant inference.
15. **OOPS** (arXiv:2601.12735, 2026) — LLM-based OpenAPI generation.
16. **Inferring Web API Descriptions from Usage Data** (HotWeb 2015) — seminal.
17. **Real Money, Fake Models** (arXiv:2603.01919, 2026) — shadow API study.
18. **Access-Control Vuln Detection** (arXiv:2201.10833, 2022) — spec-driven security.
19. **Discoverer** (USENIX Security 2007) — seminal protocol RE.
20. **Context-Aware Protocol RE** (NDSS 2017) — improves on Discoverer.
21. **APIMiner** (MDPI 2024) — state-based API identification.
22. **WebNorm** (ASE 2024) — behavioral invariant inference.
23. **Differential Regression Testing for REST** (ISSTA 2020) — replay-based regression.
24. **Metamorphic Testing of REST APIs** (TSE 2017) — oracle-free testing.
25. **ARMeta** (arXiv:2605.28321, 2026) — LLM-driven metamorphic testing.

### B. Self-Healing Web Automation / Repair / RAG (36 papers)

**Key references:**
1. **WAREX** (arXiv:2510.03285, 2025) — web agent reliability evaluation; shows LLM self-healing doesn't hold under instability.
2. **AutoRPA** (arXiv:2605.21082, 2026) — RPA self-healing.
3. **Vista/Healer** (FSE 2018) — DOM-based self-healing lineage.
4. **UITESTFIX** (ASE 2023) — LLM-based test repair.
5. **WebRL** (ICSME 2024) — 74.6% locator-breakage statistic.
6. **WABER** (ICLR 2025 Workshop) — web agent benchmark for repair.
7. **WebMate** (ICST 2012) — RPA robustness.
8. **Multi-Locators** (ICST 2015) — locator robustness.
9. **Similo** (TOSEM 2023) — element-matching features.
10. **Semter** (FSE 2023) — intent abstraction for cross-client transfer.
11. **RepairAgent** (ICSE 2025) — LLM-based code repair.
12. **ChatGPT-enhanced web UI repair** (arXiv:2312.05778, 2023).
13. **Attribute Prioritization** (ICST 2025).
14. **APR-in-LLM-era** (ICSE 2023).
15. **RAP-Gen** — retrieval-augmented patch generation.
16. **ReAPR** — retrieval-augmented automated program repair.
17. **ReCode** — fine-grained retrieval for code repair.
18. **RAG-for-code survey**.
19. **GitBugs**.
20. **Web flaky tests** (ICST 2025).
21. **UI flaky tests** (ICSE 2021).
22. **Multivocal flakiness review** (JSS 2023).
23. **Towards a Science of AI Agent Reliability** (Rabanser/Kapoor/Narayanan).

### C. Web Agents + Typed Actions + Stealth + MCP (34 papers)

**Key references:**
1. **Web Verbs** (ICML 2026, arXiv:2602.17245) — typed actions over clicks. The flagship position paper.
2. **Beyond Browsing: API-Based Web Agents** (ACL Findings 2025) — empirical proof hybrid > browsing-only.
3. **API Agents vs. GUI Agents** (arXiv:2503.11069, 2025).
4. **WebArena** (ICLR 2024) — the canonical benchmark. 14% → ~60% SOTA.
5. **OSWorld** (NeurIPS 2024) — 12% → ~38% SOTA.
6. **Mind2Web** (NeurIPS 2023).
7. **VisualWebArena** (ACL 2024).
8. **WebShop** (NeurIPS 2022).
9. **WebVoyager** (arXiv:2401.13919, 2024) — 59.1% SR.
10. **SeeAct** (ICML 2024) — grounding is required.
11. **WebRL** (ICLR 2025) — curriculum RL, 42-47%.
12. **SteP** (ACL 2024) — stacked LLM policies.
13. **AgentBench** (ICLR 2024).
14. **WAREX** (arXiv:2510.03285, 2025) — reliability re-evaluation.
15. **WebArena Verified** (OpenReview 2025) — prior rates inflated 1.4-5.2×.
16. **Agent S** (ICLR 2025).
17. **Online-Mind2Web / "Illusion of Progress"** (arXiv:2504.01382, 2025).
18. **MCP Specification** (Anthropic, Nov 2024) — the open standard.
19. **MCP Survey** (arXiv:2503.23278, 2025) — landscape + security threats.
20. **OSWorld-MCP** (arXiv:2510.24563, 2025) — MCP lifts SR 8.3% → 20.4%.
21. **ReAct** (ICLR 2023) — reasoning + acting.
22. **Toolformer** (NeurIPS 2023) — self-taught tool use.
23. **TALM** (arXiv:2205.12255, 2022) — tool-augmented LMs.
24. **ToolLLM** (ICLR 2024) — 16k+ APIs.
25. **Gorilla** (NeurIPS 2024) — 1700+ APIs.
26. **Tool Learning Survey** (arXiv:2405.17935, 2024).
27. **Augmented Language Models Survey** (arXiv:2302.07842, 2023).
28. **Browser Fingerprinting Survey** (ACM TWEB 2020).
29. **Hiding in the Crowd** (USENIX Security 2018) — fingerprint entropy.
30. **Taming the Shape Shifter** (DIMVA 2020) — anti-detect detection.
31. **Halligan** (USENIX Security 2025) — VLM CAPTCHA solver.
32. **Oedipus** (CCS 2025) — LLM CAPTCHA solver.
33. **COGNITION** (arXiv:2512.02318, 2025) — MLLM CAPTCHA defense.
34. **Web Bot Detection survey** (PMC 2024).

### D. Registry + Contract Testing + Browser-at-Scale + Versioning (41 papers)

**Key references:**
1. **RapidAPI Security Study** (ACM FSE/ISSTA 2024) — multi-tenant marketplace risks.
2. **Multi-Tenant Architecture Design** (2024) — isolation patterns.
3. **WSO2 API Marketplace white paper** (2021).
4. **AWS multi-tenant throttling** (2023).
5. **Open Banking APIs** (2024) — national-scale marketplace governance.
6. **API Utilization and Monetization** (PMC 2020).
7. **Multi-Tenant API Gateway** (Preprints 2025).
8. **CDC Testing Empirical Study** (IEEE 2023).
9. **Contract Testing Survey** (2023).
10. **Formal Model of Contract Evolution** (2024) — compatibility relations.
11. **Theory of Contracts for Web Services** (IRIF).
12. **Modeling Services using Contracts** (CEUR).
13. **Pact CDC Master's Thesis** (Aalto 2023).
14. **Contract Testing with PACT** (2025).
15. **Design by Contract** (Meyer, OOSC2) — foundational.
16. **Run-Time Monitoring in SOA** (2010).
17. **Contract Specifications Case Studies** (ICSE 2014).
18. **Building Browser Agents** (arXiv:2511.19477, 2025) — cloud browser architecture.
19. **Selenium Grid study** (2024).
20. **Apify browser-pool** (OSS library).
21. **Crawlee browser-pool** (library docs).
22. **Browserbase cloud browser guide** (2025).
23. **Browserbase business breakdown** (Contrary Research 2024).
24. **Playwright browser pool** (Medium 2024).
25. **API Evolution Systematic Review** (ACM CSUR 2021) — definitive.
26. **Web API Versioning Practices** (ICWE APIACE 2023).
27. **Large-Scale API Versioning** (JWE 2024).
28. **API Breaking Changes Large-Scale Study** (SANER 2017).
29. **Motivations for Breaking Changes** (EMSE 2019).
30. **SemVer in Golang** (ASE 2023) — widespread non-compliance.
31. **Syntactic Breaking Changes Extended** (EMSE 2024).
32. **API Breaking Changes in Bioconductor** (Virginia Tech 2023).
33. **Web APIs Evolution Assessment** (ICWE APIACE 2021).
34. **Breaking Changes in NPM** (ACM 2024).
35. **Breaking Changes SLR** (arXiv:2605.24397, 2026).
36. **Automated Canary Deployments** (2024).
37. **CanaryAdvisor** (ACM 2015).
38. **Canary on Kubernetes/Istio** (IEEE 2024).
39. **Blue-Green vs. Canary** (2024).
40. **eBay Contract Testing Case Study** (2024).
41. **API Security Gateway Multi-Tenant** (Preprints 2025).

**Total: ~136 papers** across the 4 research domains.

---

## Final Word

This roadmap is honest about where Earendel is today (5 REAL, 3 PARTIAL, 2 SIMULATED, 4 MISLEADING) and what it takes to get to "honestly production-ready."

**The critical path is Phase 0 → 1 → 3 → 7.** If you do nothing else, do these four:
1. Stop lying about what works (Phase 0).
2. Wire real HAR capture so the Option B moat is real (Phase 1).
3. Point the browser adapter at real portals so the 6-adapter chain isn't a simulation (Phase 3).
4. Build the eval harness so the "10×/10×/500×" claims are measured, not asserted (Phase 7).

After those four, Earendel is honestly production-ready. The remaining phases (2, 5, 6, 8, 9, 10) make it better, but the four above make it honest.

**"Browser Use lets agents browse. Earendel makes browsing unnecessary."** — but only if the network discovery actually discovers real endpoints from real traffic. Today it doesn't. Phase 1 fixes that.
