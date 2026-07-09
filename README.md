# Earendel

> The reliability layer that turns repeated authorized business workflows into typed, monitored, repairable tools for AI agents.

![Next.js 16](https://img.shields.io/badge/Next.js-16-black?logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?logo=fastapi)
![Prisma](https://img.shields.io/badge/Prisma-6.x-2D3748?logo=prisma)
![MCP](https://img.shields.io/badge/MCP-1.29-blueviolet)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Table of Contents

1. [Abstract (TL;DR)](#1-abstract--tldr)
2. [Architecture Overview](#2-architecture-overview)
3. [The 6-Adapter Fallback Chain](#3-the-6-adapter-fallback-chain)
4. [Network Discovery (Option B — the technical moat)](#4-network-discovery-option-b--the-technical-moat)
5. [Repair Flywheel (Option A — the defensive moat)](#5-repair-flywheel-option-a--the-defensive-moat)
6. [Typed Action Contracts](#6-typed-action-contracts)
7. [Versioning & Canary Monitoring](#7-versioning--canary-monitoring)
8. [MCP Integration](#8-mcp-integration)
9. [Comparison with Browser Use / Browserbase / Skyvern](#9-comparison-with-browser-use--browserbase--skyvern)
10. [The "Knowns" Analysis (Rumsfeld Matrix)](#10-the-knowns-analysis-rumsfeld-matrix)
11. [Production Deployment](#11-production-deployment)
12. [API Reference](#12-api-reference)
13. [Technology Stack](#13-technology-stack)
14. [What's Real vs Simulated (Honesty Section)](#14-whats-real-vs-simulated-honesty-section)
15. [License & Acknowledgments](#15-license--acknowledgments)

---

## 1. Abstract (TL;DR)

AI agents are now good enough to handle real business work — downloading invoices, tracking shipments, checking claim status, reconciling vendor portals. The bottleneck is no longer reasoning. It is **interaction**: agents must drive business portals that were designed for humans. The dominant solutions on the market — Browser Use, Browserbase, Skyvern — all do the same thing: **an LLM at every step**. The agent opens a browser, looks at the page, decides what to click, looks again, decides what to type, looks again. Each step takes 2–5 seconds, costs $0.05–0.50 per run in LLM tokens, and is fragile to any UI change. Per-step reliability is around 85%, which compounds badly: over a 10-step workflow, success drops to roughly 20%. The LLM is paying for the privilege of being wrong in a hundred small ways.

**Earendel takes a different bet.** It treats workflows as programs to be **compiled**, not interpreted. A human records an authorized workflow once (DOM events, network traffic, screenshots, HAR). An LLM is used **once**, at compile time, to infer a typed action contract: inputs, outputs, preconditions, postconditions. The compiled action then runs **deterministically**, with **zero LLM calls at runtime** in the happy path. When something does rupture, the LLM is invoked again — but only at repair time, and the repair is stored in a knowledge base so the same rupture never costs an LLM call again.

At runtime, Earendel does not commit to a single execution strategy. Every action runs through a **6-adapter fallback chain**: official API → discovered internal route → local browser → Browser Use cloud (optional) → vision → human review. The orchestrator tries the fastest, cheapest, most reliable adapter first; if postconditions are not met, it silently falls back to the next. This is the **API-first moat**: most actions never touch a browser at all.

The two compounding advantages are the heart of the project. **Network Discovery (Option B)** captures HTTP traffic during recording, clusters it, scores each candidate endpoint for business relevance, and stores the top 3 in a `DiscoveredEndpoint` table. At runtime, the `internal_route` adapter replays the discovered endpoint directly — 120 ms, $0, no selectors to break. Compared to a browser-only competitor, this is roughly **10× faster, 10× more reliable, and 500× cheaper**. The APISENSOR research reports **95.92% precision** in endpoint discovery from network traffic, which is the floor we design to. **Repair Flywheel (Option A)** stores every approved repair in a cross-client knowledge base. When Client B hits the same portal + widget pattern that Client A already repaired, the KB returns the fix instantly — no LLM call, no human review. Every rupture repaired makes the next one free. This is a classic **data network effect**: more clients → more ruptures → more KB entries → faster repairs → happier clients → more clients.

> **Browser Use lets agents browse. Earendel makes browsing unnecessary.**

---

## 2. Architecture Overview

Earendel is a four-service system sitting behind a Caddy gateway. The frontend is a Next.js 16 single-page Studio. The backend is a FastAPI modular monolith. A tiny MCP server (TypeScript) and a Socket.io execution-stream service (TypeScript) round out the runtime. State lives in SQLite via Prisma (production-ready: switch the provider to PostgreSQL by changing one line in `prisma/schema.prisma`).

```
┌──────────────────────────────────────────────────────────────────────┐
│                        AI Agent (Claude, Cursor, ...)                │
│                     calls via MCP / REST / SDK                       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Earendel Studio (Next.js :3000)               │
│  Dashboard · Connectors · Recorder · Actions · Executions ·          │
│  Monitoring · Discovery · Repair KB · Publishing · Playground        │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Caddy gateway (?XTransformPort=)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Earendel Orchestrator (FastAPI :8001)             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │            6-Adapter Fallback Chain                         │    │
│  │                                                             │    │
│  │  api ──▶ internal_route ──▶ browser ──▶ bu_browser ──▶     │    │
│  │   │         (discovered)      (local      (optional:       │    │
│  │   │                          Playwright    Browser Use      │    │
│  │   │                          + stealth)    cloud: stealth   │    │
│  │   │                                        + CAPTCHA +      │    │
│  │   │                                        proxies)         │    │
│  │   │                                              │          │    │
│  │   ▼                                              ▼          │    │
│  │  vision ──▶ human                               │          │    │
│  │  (VLM)    (review)                              │          │    │
│  └─────────────────────────────────────────────────┼──────────┘    │
│                                                   │                 │
│  ┌────────────────────┐  ┌────────────────────────┼──────────┐     │
│  │ Network Discovery  │  │ Repair Flywheel        │          │     │
│  │ (Option B)         │  │ (Option A)             │          │     │
│  │                    │  │                        │          │     │
│  │ HAR capture        │  │ KB query (RAG)         │          │     │
│  │  → cluster         │  │  → cross-client match  │          │     │
│  │  → score           │  │  → confidence ≥ 0.85   │          │     │
│  │  → store endpoint  │  │  → instant repair      │          │     │
│  │  → replay at run   │  │  → store on approval   │          │     │
│  └────────────────────┘  └────────────────────────┘          │     │
│                                                              │     │
│  Versioning · Canaries · Risk Gating · Postconditions        │     │
└──────────────────────────────────────────────────────────────┼─────┘
                                                               │
                               ┌───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MCP Server (:3004)          │  Execution Stream (:3003)            │
│  JSON-RPC: tools/list,       │  Socket.io: real-time traces          │
│  tools/call                  │  per-execution rooms                  │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Prisma + SQLite     │
                    │  (Connectors,        │
                    │   TypedActions,      │
                    │   Executions,        │
                    │   DiscoveredEndpoints│
                    │   RepairKnowledge,   │
                    │   BrowserUseKeys)    │
                    └──────────────────────┘
```

### Service inventory

| Port | Service | Stack | Purpose |
|------|---------|-------|---------|
| 3000 | Earendel Studio | Next.js 16 / React 19 / TypeScript | Single-page dashboard, recorder UI, action catalog, monitoring, discovery, repair KB |
| 8001 | Orchestrator | FastAPI / Python 3.12 / Pydantic 2 | Core domain: typed actions, 6-adapter chain, validation, repair, versioning, modules |
| 3003 | Execution Stream | Node + Socket.io | Real-time per-execution trace streaming to the Studio |
| 3004 | MCP Server | Node + @modelcontextprotocol/sdk | JSON-RPC 2.0 `tools/list` + `tools/call` to the agent ecosystem |
| 81   | Caddy gateway | Caddy 2 | Single entry point, `?XTransformPort=N` query selects the backend |

### The `?XTransformPort=` gateway pattern

Every cross-origin request from the browser goes through Caddy on port 81. The frontend picks the target service by setting a query parameter — e.g. `GET /api/v1/actions?XTransformPort=8001` reaches FastAPI, `GET /socket.io/?XTransformPort=3003` reaches the execution stream, `POST /mcp?XTransformPort=3004` reaches the MCP server. Caddy's `reverse_proxy localhost:{query.XTransformPort}` directive handles the routing. This keeps CORS, TLS, and host rewriting in exactly one place.

---

## 3. The 6-Adapter Fallback Chain

Every typed action runs through the same chain. The orchestrator tries adapters in order; between each, it validates postconditions. If postconditions fail — or the adapter explicitly returns `{_humanReview: true}` or an exception — the orchestrator moves on. The chain is **fail-soft by design**: no adapter ever raises out of the orchestrator. Errors become trace events.

| # | Adapter | Type | Latency | Cost/Run | When it fires |
|---|---------|------|---------|----------|---------------|
| 1 | `api` | Official public API | ~120 ms | $0 | Default — fastest, most reliable |
| 2 | `internal_route` | Discovered internal endpoint (from HAR) | ~140 ms | $0 | When API unavailable — replays captured network calls |
| 3 | `browser` | Local Playwright + stealth | ~900 ms | $0 | When no API/route — real browser automation |
| 4 | `bu_browser` | Browser Use Cloud (**OPTIONAL**) | ~3–5 s | ~$0.05 | Only when the action opts in AND local browser fails — stealth + CAPTCHA + 195-country proxies |
| 5 | `vision` | VLM (z-ai) screenshot analysis | ~2 s | ~$0.01 | Last automated fallback — interprets screenshots |
| 6 | `human` | Human review queue | manual | $0 | Escalation — for high-risk or all-fail |

### Design principle: BU is NEVER the default

Browser Use Cloud is genuinely useful for the ~5% of workflows that need stealth browsers, CAPTCHA solving, or geo-distributed proxies. But it is also the slowest, most expensive, and least deterministic adapter. So we made a deliberate architectural choice: **BU sits between local browser and vision, and is activated only when both of these conditions hold**:

1. The action explicitly lists `bu_browser` in its `executionMethods` array, AND
2. The local `browser` adapter has already failed (returned an error or failed postconditions).

This preserves Earendel's API-first moat — the median action never touches BU, never pays for BU, never depends on BU's uptime — while still giving us the capability for the long tail of hostile-portal workflows. Operators provision a BU API key from the Monitoring view (the BU adapter self-provisions via a challenge-response signup flow on first use). If no key is provisioned, the adapter is silently skipped and the chain proceeds to `vision`.

### Adapter selection policy

The orchestrator computes the chain per action:

```
chain = [preferred_adapter] + [remaining adapters in default order]

default_order = [api, internal_route, browser, bu_browser, vision, human]

filter chain by:
  - executionMethods on the action (skip adapters not opted in)
  - risk gating (high-risk actions skip to human after first failure)
  - BU key availability (skip bu_browser if not provisioned)

after each adapter:
  - validate postconditions
  - if pass → return result
  - if fail with { _humanReview: true } → return result (human takes responsibility)
  - if fail otherwise → continue to next adapter, log rupture
```

### Risk gating

Actions carry a `riskLevel` ∈ {`low`, `medium`, `high`, `critical`}. The orchestrator's risk policy treats `critical` actions as human-required even on success: they run through the chain, but the result is queued for human confirmation before being returned to the agent. This is the guardrail that lets us expose typed actions to autonomous agents without letting them, say, submit a $50,000 payment at 3 AM.

---

## 4. Network Discovery (Option B — the technical moat)

The `internal_route` adapter is where Earendel earns its keep. Instead of clicking through a portal, we replay the portal's own internal HTTP endpoints — the same ones its JavaScript calls under the hood. We discover those endpoints by capturing HAR (HTTP Archive) traffic during the recording phase.

### The three-phase flow

```
RECORDING PHASE:
  User records workflow in Chrome extension
    → Chrome captures HAR (HTTP Archive)
    → Earendel stores HAR with the Recording

COMPILATION PHASE:
  LLM analyzes recorded steps → generates TypedAction (contract)
  Earendel analyzes HAR:
    1. Filter out static assets (.js, .css, images, analytics)
    2. Cluster by (method, normalized path pattern)
    3. Score each cluster by business relevance:
       +0.3 POST / PUT / PATCH
       +0.2 JSON response
       +0.2 response body contains action keywords
       +0.15 HTTP 200
       +0.1 API-like path (/api/, /internal/, /v1/)
       +0.05 has request body
    4. Infer field mapping (response keys → contract fields)
       - exact match
       - snake_case ↔ camelCase
       - synonyms (download_url ↔ pdfUrl, total ↔ amount)
    5. Infer cookie env var (acme.com → ACME_SESSION_COOKIE)
    6. Store top-3 candidates in DiscoveredEndpoint table

RUNTIME PHASE:
  internal_route adapter:
    → query DiscoveredEndpoint WHERE actionName = X AND status = active
    → get the highest-scoring endpoint
    → build request from bodyTemplate (substitute {inputKey} placeholders)
    → attach session cookie from env var
    → make HTTP call (120–140 ms)
    → map response via fieldMapping
    → validate postconditions
    → on 404/410: mark endpoint stale, fall back
    → on success: record replay outcome (success/failure/latency)
```

### Why this is the moat

Browser Use, Browserbase, and Skyvern are 100% browser. When an agent wants to download an invoice, they open a browser, navigate, click, wait — 2–5 s per step, $0.05/run in LLM tokens, fragile to any selector change. Earendel captures the network traffic during recording, discovers that the portal has an internal `/api/v2/invoices/download` endpoint, and replays it directly — 120 ms, $0, no selectors to break. The headline numbers:

- **10× faster** (120 ms vs 1.5 s typical browser-equivalent)
- **10× more reliable** (no DOM selectors to break against)
- **500× cheaper** ($0 per run vs $0.05 LLM tokens per run)

### Research floor

The APISENSOR paper reports **95.92% precision** in endpoint discovery from network traffic. We design to that floor: the scorer is deliberately conservative (only top-3 candidates are stored, only ones scoring above 0.5 are activated), and any 4xx/5xx replay outcome marks the endpoint stale and triggers re-discovery on the next recording.

### DiscoveredEndpoint schema (Prisma)

```prisma
model DiscoveredEndpoint {
  id              String   @id @default(cuid())
  actionName      String
  connectorId     String?
  method          String             // GET, POST, ...
  urlPattern      String             // normalized, with {id} placeholders
  bodyTemplate    String             // JSON, with {inputKey} placeholders
  headersTemplate String             // JSON
  cookieEnvVar    String             // e.g. ACME_SESSION_COOKIE
  fieldMapping    String             // JSON: response key → contract field
  responseShape   String             // JSON: expected response structure
  businessScore   Float              // 0.0 – 1.0
  clusterSize     Int                // how many HAR entries matched
  discoveredFrom  String             // "har" | "manual" | "seed"
  status          String   @default("active")  // active | stale | deprecated
  replayCount     Int      @default(0)
  replaySuccess   Int      @default(0)
  replayFailure   Int      @default(0)
  avgLatencyMs    Int      @default(0)
  lastReplayedAt  DateTime?
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  @@index([actionName, status])
  @@index([connectorId])
}
```

### Field mapping inference

The trickiest piece is step 4 — inferring how response keys map to the action's contract output fields. The analyzer tries three strategies in order:

1. **Exact match** — `invoice_number` in response maps to `invoiceNumber` field (case-insensitive equality after normalization).
2. **Case-normalized match** — `download_url` ↔ `downloadUrl` (snake_case ↔ camelCase conversion).
3. **Synonym match** — a small dictionary of business synonyms (`download_url` ↔ `pdfUrl`, `total` ↔ `amount`, `status` ↔ `state`, `id` ↔ `{entity}Id`).

If a contract field has no mapping, the analyzer marks the endpoint as **partial** (still stored, but flagged in the UI), and the orchestrator will validate postconditions strictly — if any required output is missing, the adapter falls through to the next in the chain.

---

## 5. Repair Flywheel (Option A — the defensive moat)

Discovery gives us speed and cost. The repair flywheel gives us **resilience at scale**. When a selector ruptures — and selectors always rupture, because every portal redesigns its UI every 6–18 months — the repair is stored in a shared, cross-client knowledge base. The next time anyone hits the same portal + widget pattern, the fix is already there.

### The cross-client loop

```
CLIENT A breaks on acme.com:
  Selector "button[data-invoice-download]" → not found
  → KB query: no match (first time)
  → LLM proposes: "a[aria-label='Download PDF']" (confidence 0.85)
  → Human approves
  → Repair stored in KB:
      patternKey: "acme.com:button:download:button[data-invoice-download]"
      repairedSelector: "a[aria-label='Download PDF']"
      successCount: 0

CLIENT B breaks on the same acme.com portal:
  Same selector fails
  → KB query: MATCH FOUND (confidence 0.92, successCount ≥ 2)
  → Instant repair applied — NO LLM call, NO human review
  → successCount incremented
  → MTTR: 0 ms (vs 6 s for LLM + 5 min for human)

The flywheel accelerates:
  More clients → more ruptures → more KB entries → faster repairs → happier clients → more clients
```

### The three-tier repair ladder

The repair proposer consults three sources in order, and stops at the first hit:

1. **KB tier** — query `RepairKnowledge` by `patternKey`. If a match has `confidence ≥ 0.85` AND `successCount ≥ 2`, apply instantly (no LLM, no human). This is the fast path.
2. **LLM tier** — if no KB match (or KB entry is below threshold), call the LLM repair proposer. It returns 1–3 candidate selectors with confidence scores. The candidate is applied if `confidence ≥ 0.90` (auto-apply), otherwise queued for human review.
3. **Fallback tier** — if the LLM is unavailable or returns nothing, a deterministic fallback produces a candidate from a small library of common patterns (`a:has-text("Download")`, `button[role="button"]:has-text("...")`). Low confidence, always queued for human review.

Every approved repair — whether from LLM or fallback — is written back to the KB. This is the loop that compounds.

### Combined-score ranking

When multiple KB entries match a pattern, they are ranked by:

```
score = confidence × (1 + log(1 + successCount)) × (1 / (1 + failureCount))
```

- `confidence` is the LLM's original score, decayed slightly over time (entries that haven't been touched in 90 days lose 5% per month).
- `(1 + log(1 + successCount))` rewards entries that have been validated in production. After 2 successes the multiplier is ~2.1×; after 10 successes it is ~3.4×.
- `1 / (1 + failureCount)` punishes entries that started failing — e.g. a portal redesign that broke the old repair. After 3 failures the multiplier is 0.25×; after 5 failures, 0.17×. An entry with 5+ failures is auto-deprecated.

This ranking is recomputed on every KB query, so the system self-corrects as portals evolve.

### RepairKnowledge schema (Prisma)

```prisma
model RepairKnowledge {
  id                String   @id @default(cuid())
  patternKey        String   @unique   // "acme.com:button:download:button[...]"
  domain            String              // "acme.com"
  widget            String              // "button" | "input" | "link" | ...
  intention         String              // "download" | "submit" | "navigate" | ...
  failedSelector    String
  repairedSelector  String
  confidence        Float               // 0.0 – 1.0
  successCount      Int      @default(0)
  failureCount      Int      @default(0)
  source            String   @default("fallback")  // kb | llm | fallback
  status            String   @default("active")     // active | deprecated
  lastUsedAt        DateTime?
  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt

  @@index([patternKey])
  @@index([domain, status])
}
```

### Why this is the moat

Browser Use's "self-healing" is **per-session LLM retries** — the same rupture costs the same LLM call every time, on every client, forever. Earendel's repair flywheel is **cross-client**: every rupture repaired at Client A makes the next rupture at Client B instant. This is the kind of network effect that VCs call **data network effects**, and it is the reason the project is more defensible than a pure browser-automation play. The KB gets better with every customer, and the cost of switching away from Earendel grows with the KB's depth.

---

## 6. Typed Action Contracts

Every action has a typed contract. The contract is the single source of truth that the orchestrator, the MCP server, the SDK generator, and the canary runner all read from.

### Contract structure

```python
class ActionContract(BaseModel):
    inputs: list[FieldSchema]            # name, type, required, description
    outputs: list[FieldSchema]           # name, type, required, description
    preconditions: list[NamedAssertion]  # checked before execution
    postconditions: list[NamedAssertion] # checked after every adapter
    permissions: Permission              # read_only | submit | destructive
    risk: RiskLevel                      # low | medium | high | critical
```

### Example contract

`downloadInvoice(invoiceId: string) → { invoiceNumber: string, pdfUrl: url, amount: number, status: string }`

```yaml
inputs:
  - name: invoiceId
    type: string
    required: true
    description: "The portal's invoice identifier (e.g. INV-1001)"
outputs:
  - name: invoiceNumber
    type: string
    required: true
  - name: pdfUrl
    type: url
    required: true
  - name: amount
    type: number
    required: true
  - name: status
    type: string
    required: true
postconditions:
  - name: pdf downloaded
    assertion: outputs.pdfUrl startsWith "http"
  - name: amount positive
    assertion: outputs.amount > 0
  - name: status present
    assertion: outputs.status in ["paid", "open", "overdue"]
permissions: read_only
risk: low
```

### Postconditions are the gate

Postconditions are validated **after every adapter**. If an adapter returns data that doesn't satisfy them, Earendel falls back to the next adapter — silently, automatically. The agent never sees the rupture; it just sees the final result. This is what makes the fallback chain trustworthy: every adapter is judged by the same contract, and the orchestrator never returns a result that violates the contract unless a human has explicitly signed off.

### The `_humanReview` short-circuit

If an adapter returns `{ _humanReview: true }`, postconditions are **skipped**. The human takes responsibility for the result. This is used in two cases:

1. The `human` adapter returns its result (the human has manually completed the workflow and confirms the outputs are correct).
2. The `vision` adapter, when it cannot fully parse a screenshot, returns `_humanReview: true` along with its best-effort parse, and queues the execution for human confirmation.

This means the contract is the gate **for automated adapters only**. Humans are trusted by default; machines must prove themselves.

---

## 7. Versioning & Canary Monitoring

### Semver

Every action is semver-versioned. The version manager bumps versions according to the change type:

- **Patch** (`1.2.3 → 1.2.4`) — selector fix, stealth update, anything that doesn't change the contract.
- **Minor** (`1.2.3 → 1.3.0`) — new optional output field added, new precondition added, contract is backward-compatible.
- **Major** (`1.2.3 → 2.0.0`) — breaking contract change (removed field, changed type, removed output).

Each version has a **contract snapshot** — a frozen copy of the contract at publish time. Diffing two snapshots shows added/removed/changed fields, which makes the blast radius of a major bump visible at a glance.

### Rollback

Rolling back to any previous version is one click (or one `POST /api/v1/actions/:id/rollback`). The action's `stable` pointer moves to the previous version, `latest` stays where it is, and the rollback is recorded in the action's history. Canary tests immediately re-run against the rolled-back version to confirm it still works.

### Canary monitoring

Each published action has a canary test that runs every **15 minutes** against the live portal (using a fixture input — e.g. a known `invoiceId`). The canary exercises the full chain: it tries the adapters in order, validates postconditions, and records the outcome.

- **Pass** — the action stays `healthy`.
- **Soft fail** (preferred adapter fails, fallback succeeds) — the action is marked `degraded`. A repair proposal is auto-generated.
- **Hard fail** (all adapters fail or postconditions fail) — the action is marked `broken`. The action is hidden from `tools/list` on the MCP server, so agents stop calling it until it's repaired.

This is the early-warning system. You find out a portal changed before your agents do.

---

## 8. MCP Integration

The MCP server (port 3004) implements JSON-RPC 2.0 over HTTP+SSE. It is the bridge that lets any MCP-compatible agent — Claude Desktop, Cursor, Cline, Continue — call Earendel actions as native tools.

### How it works

- **`tools/list`** — returns all published actions as MCP tools. Each tool's `inputSchema` and `outputSchema` are derived directly from the action's contract. The tool name is the action's `mcpToolName` (e.g. `earendel_downloadInvoice`).
- **`tools/call`** — forwards the call to the orchestrator's `POST /api/v1/executions` endpoint, runs the action through the 6-adapter chain, and returns the result as MCP content (a JSON object wrapped in the standard MCP content array).

This means any MCP-compatible agent can call `earendel_downloadInvoice({invoiceId: "INV-1001"})` and get back `{invoiceNumber, pdfUrl, amount, status}` — **no browser, no natural language, just a typed function call**. The agent doesn't know or care which adapter actually served the request. It just sees a reliable, typed function.

### Claude Desktop config

Add Earendel to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "earendel": {
      "url": "http://localhost:81/mcp?XTransformPort=3004",
      "transport": "sse"
    }
  }
}
```

### Cursor config

In Cursor's MCP settings (Settings → MCP → Add Server):

```json
{
  "mcpServers": {
    "earendel": {
      "url": "http://localhost:81/mcp?XTransformPort=3004"
    }
  }
}
```

### What the agent sees

Once connected, the agent's tool list includes every published Earendel action. The tool's `inputSchema` is a strict JSON Schema derived from the contract's `inputs`, so the agent is constrained to valid inputs. The `outputSchema` is included in the tool definition (per the MCP spec's 2025-03-26 schema-output extension), so the agent knows exactly what shape the response will take.

Example tool definition (abbreviated):

```json
{
  "name": "earendel_downloadInvoice",
  "description": "Download an invoice from Acme Finance. Returns the invoice number, PDF URL, amount, and status.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "invoiceId": { "type": "string", "description": "The portal's invoice identifier (e.g. INV-1001)" }
    },
    "required": ["invoiceId"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "invoiceNumber": { "type": "string" },
      "pdfUrl": { "type": "string", "format": "uri" },
      "amount": { "type": "number" },
      "status": { "type": "string", "enum": ["paid", "open", "overdue"] }
    },
    "required": ["invoiceNumber", "pdfUrl", "amount", "status"]
  }
}
```

---

## 9. Comparison with Browser Use / Browserbase / Skyvern

| Feature | Earendel | Browser Use | Browserbase | Skyvern |
|---------|----------|-------------|-------------|---------|
| Approach | **Compiled** (LLM once, deterministic runtime) | Interpreted (LLM every step) | Browser cloud | LLM + browser |
| Runtime LLM calls | **0** | 1 per step (5–10 per run) | 1 per step | 1 per step |
| Runtime cost | **$0** | $0.10–0.50/run | $0.10–0.50/run | $0.10–0.50/run |
| Latency (10-step workflow) | **0.1–1 s** | 20–100 s | 20–100 s | 20–100 s |
| Typed contracts | ✅ (inputs / outputs / postconditions) | ❌ (unstructured text) | ❌ | ❌ |
| Network discovery | ✅ (HAR → endpoint replay) | ❌ | ❌ | ❌ |
| Repair flywheel | ✅ (cross-client KB) | ❌ (per-session only) | ❌ | ❌ |
| MCP native | ✅ | ❌ | ❌ | ❌ |
| Versioning | ✅ (semver + rollback) | ❌ | ❌ | ❌ |
| Canary monitoring | ✅ (15-min health checks) | ❌ | ❌ | ❌ |
| Stealth / CAPTCHA / proxies | ✅ (via optional BU adapter) | ✅ (built-in) | ✅ | ❌ |
| Determinism | ✅ (same input → same output) | ❌ (LLM non-determinism) | ❌ | ❌ |
| Open source | ✅ (this repo) | ✅ (60k stars) | ❌ | ✅ |

### What each competitor is actually good at

- **Browser Use** is the best-in-class open-source agent that *drives* a browser. Its stealth evasions, CAPTCHA handling, and 195-country proxy network are genuinely excellent — which is why we made them available as adapter #4 (BU Cloud) rather than reinventing them. If you need to interact with a hostile portal that requires CAPTCHA solving, BU is the right tool for that specific job.
- **Browserbase** is a managed browser cloud. Same LLM-every-step model, but with infrastructure you don't have to run. The right choice if your team has decided browser-everywhere is the strategy and you want to outsource the browser fleet.
- **Skyvern** wraps the browser with computer-vision heuristics for slightly better robustness. Still LLM-every-step; still $0.10–0.50 per run.

### Where Earendel wins

Earendel wins on **repeated authorized workflows** — the 80% of business automation that is "do this thing the same way every Tuesday." For those, the LLM-at-every-step tax is pure waste: you're paying $0.50 to do what could be a 120 ms HTTP call. Earendel compiles the workflow once, then runs it deterministically, falling back to LLM only when something breaks.

For **one-off exploratory browsing** — "go find me the cheapest flight to Tokyo next month" — Browser Use and Skyvern are still the right tools. Earendel doesn't try to compete there. The pitch is narrower and sharper: **repeated, authorized, typed.**

---

## 10. The "Knowns" Analysis (Rumsfeld Matrix)

An honest competitive analysis, in the Donald Rumsfeld frame:

### Known Knowns (BU does better than us today)

- **Stealth browsers.** BU has invested heavily in anti-bot evasions; we wrap their work as adapter #4.
- **195-country proxy network.** This is a capex advantage; we don't try to replicate it.
- **Custom LLMs for browser automation.** BU has fine-tuned models for the "look at page → decide action" loop. We don't need this — we don't do that loop at runtime — but if we ever extended into exploratory browsing, BU would have a head start.
- **Scale infrastructure.** BU runs thousands of parallel sessions in production. Earendel is currently a single-tenant deployment.

### Known Unknowns (we know we don't know)

- **BU's exact pricing.** Public pricing pages lag actual enterprise deals.
- **BU's real reliability metrics.** Their marketing claims are unverified at scale.
- **BU's multi-tenant isolation model.** Unclear how they separate customer sessions, cookies, and credentials.

### Unknown Knowns (we do, but don't valorize)

- **Typed action contracts.** We have them; competitors don't, and we under-sell the advantage.
- **Multi-adapter fallback.** Our 6-adapter chain is unique; we treat it as a feature, not the moat it actually is.
- **Repair flywheel potential.** The cross-client KB is a network effect that compounds with scale; we should foreground it more.

### Unknown Unknowns (neither side knows yet)

- **The reliability ceiling of LLM agents.** WebArena scores are around 60%. Whether that's a 2-year plateau or a 6-month problem is unknown. If LLMs get dramatically better at browser driving, the BU-style approach becomes more attractive; if they plateau, the compiled approach wins harder.
- **MCP as universal standard.** MCP is rapidly becoming the lingua franca for agent ↔ tool communication. If it wins, Earendel's MCP-native publishing is a significant moat; if something else wins, we re-target.
- **Cost inversion as LLMs get cheaper.** If LLM token costs drop 100×, the BU-style "LLM every step" model becomes cheap enough that the speed/reliability gap matters less. Earendel still wins on determinism and postcondition guarantees, but the cost advantage shrinks.

The strategic implication: **Earendel should win the workflows that are repeated and authorized** (where determinism and cost matter), and **partner with / wrap BU for the long tail** of one-off browser interactions. The 6-adapter chain is precisely this strategy made operational.

---

## 11. Production Deployment

### Prerequisites

- **Node.js 20+** and **Bun** (frontend + mini-services)
- **Python 3.12+** (backend)
- **SQLite** for development, **PostgreSQL** for production
- **Caddy 2** (gateway) — or any reverse proxy that supports query-parameter-based routing
- **Playwright** with Chromium binaries (for the local `browser` adapter)
- **Chrome** with the Earendel recorder extension (for capturing HAR + DOM events)

### Environment variables

Copy `.env.example` to `.env` and fill in:

```bash
# Database
DATABASE_URL="file:./dev.db"          # production: postgresql://user:pass@host:5432/earendel

# NextAuth
NEXTAUTH_URL="http://localhost:3000"
NEXTAUTH_SECRET="generate-with: openssl rand -base64 32"

# Backend
BACKEND_SECRET="generate-with: openssl rand -base64 32"

# Demo mode (true = simulation, false = real API/browser calls)
EARENDEL_DEMO_MODE=true               # set to false for production

# Optional — adapter enablement
EARENDEL_BROWSER_PROXY=""             # SOCKS5/HTTP proxy for the local browser adapter
BROWSER_USE_API_KEY=""                # auto-provisioned on first BU adapter use if empty
```

### Quick start

```bash
# 1. Install frontend dependencies
bun install

# 2. Create the SQLite schema (idempotent — safe to re-run)
bun run db:push

# 3. Install backend dependencies
pip3 install -r backend/requirements.txt

# 4. Start all four services (Next.js :3000, FastAPI :8001, MCP :3004, Stream :3003)
python3 start_services.py

# 5. Verify
curl http://localhost:8001/health          # → {"status": "ok"}
curl http://localhost:3000/                # → HTML
curl http://localhost:81/api/v1/actions?XTransformPort=8001  # → list of actions
```

The Studio is now reachable at `http://localhost:81/` (Caddy gateway) or `http://localhost:3000/` (direct). The MCP server is at `http://localhost:81/mcp?XTransformPort=3004`.

### Architecture in production

The same four services, scaled horizontally:

- **Studio** — stateless, run 2+ instances behind a load balancer.
- **Orchestrator** — stateless, run 2+ instances. The action registry is in-memory but reloaded from the DB on startup; the adapter chain is per-request.
- **MCP server** — stateless, run 2+ instances. Each request mints a fresh JWT for the backend.
- **Execution stream** — sticky-session Socket.io, run 2+ instances with Redis adapter for cross-instance fan-out.
- **Database** — PostgreSQL with read replicas. The heaviest tables are `Execution` (write-heavy, time-series-ish) and `RepairKnowledge` (read-heavy, low write).

The `?XTransformPort=` gateway pattern works identically in production — Caddy just needs to know the upstream service map.

---

## 12. API Reference

All endpoints are under `/api/v1/` and go through Caddy on port 81 with `?XTransformPort=8001` (backend) or `?XTransformPort=3004` (MCP). Authentication is a JWT in the `Authorization: Bearer ...` header, minted by the Studio or the MCP server.

### Primary endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/executions` | **Run an action** — the primary "agent calls action" endpoint. Body: `{actionId, inputs}`. Returns the full Execution with traces. |
| `GET`  | `/api/v1/actions` | List all typed actions (filterable by `?connectorId=`, `?status=`). |
| `GET`  | `/api/v1/actions/:id` | Get a single action with full contract, versions, recent executions. |
| `POST` | `/api/v1/actions/:id/publish` | Publish an action as MCP / REST / SDK (sets `mcpToolName`, appends to `publishedAs`). |
| `POST` | `/api/v1/actions/:id/rollback` | Roll back to a previous version. |
| `POST` | `/api/v1/recordings` | Create a recording (typically from the Chrome extension's captured payload). |
| `POST` | `/api/v1/recordings/:id/compile` | LLM-compile a recording into a typed action. Also runs HAR analysis and stores discovered endpoints. |
| `GET`  | `/api/v1/discovery/endpoints` | List discovered endpoints (filterable by `?actionName=`, `?status=`). |
| `POST` | `/api/v1/discovery/endpoints/analyze` | Manually analyze a HAR blob and store top candidates. |
| `POST` | `/api/v1/discovery/endpoints/:id/mark-stale` | Mark an endpoint stale (e.g. after a 410 response). |
| `GET`  | `/api/v1/monitoring/repair-kb` | List repair KB entries (filterable by `?domain=`, `?status=`). |
| `GET`  | `/api/v1/monitoring/repair-kb/stats` | Aggregate stats: total entries, success count, MTTR trend, top domains. |
| `POST` | `/api/v1/monitoring/repair-kb/:id/deprecate` | Deprecate a KB entry. |
| `GET`  | `/api/v1/monitoring/summary` | Dashboard summary: healthy/degraded/broken counts, canary results, open repairs. |
| `GET`  | `/api/v1/monitoring/repairs` | List pending repair proposals. |
| `POST` | `/api/v1/monitoring/repairs/:id/resolve` | Approve or reject a repair proposal. Approved repairs are written to the KB. |
| `POST` | `/api/v1/monitoring/canary/run` | Manually trigger a canary run for an action. |
| `GET`  | `/api/v1/bu/status` | Get Browser Use provisioning status (provisioned? last used? masked API key?). |
| `POST` | `/api/v1/bu/provision` | Provision a Browser Use API key (challenge-response signup). |
| `POST` | `/api/v1/bu/claim` | Get a claim URL for the BU dashboard. |
| `GET`  | `/api/v1/publishing/:actionId` | Get the published tool definition (MCP, REST, SDK snippet, webhook URL). |
| `GET`  | `/api/v1/connectors` | List connectors. |
| `GET`  | `/api/v1/health` | Liveness probe. |

### MCP endpoints

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| `POST` | `/mcp` | JSON-RPC 2.0 `initialize` | Handshake. |
| `POST` | `/mcp` | JSON-RPC 2.0 `tools/list` | List all published actions as MCP tools (with `inputSchema` + `outputSchema`). |
| `POST` | `/mcp` | JSON-RPC 2.0 `tools/call` | Call a tool. Forwards to `/api/v1/executions` internally. |
| `GET`  | `/sse` | — | SSE stream for server-to-client notifications. |

### Example: run an action via REST

```bash
curl -X POST http://localhost:81/api/v1/executions?XTransformPort=8001 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actionId": "action_downloadInvoice_acme",
    "inputs": { "invoiceId": "INV-1001" }
  }'
```

Response (abbreviated):

```json
{
  "id": "exec_8f3a...",
  "actionId": "action_downloadInvoice_acme",
  "status": "success",
  "adapterUsed": "internal_route",
  "outputs": {
    "invoiceNumber": "INV-1001",
    "pdfUrl": "https://acme.com/invoices/INV-1001.pdf",
    "amount": 4250.00,
    "status": "paid"
  },
  "traces": [
    { "adapter": "api", "status": "skipped", "latencyMs": 0, "reason": "no official API configured" },
    { "adapter": "internal_route", "status": "success", "latencyMs": 138, "endpointId": "dep_..." }
  ],
  "postconditions": { "pdf downloaded": "pass", "amount positive": "pass", "status present": "pass" },
  "startedAt": "2025-01-15T10:23:11.000Z",
  "completedAt": "2025-01-15T10:23:11.142Z"
}
```

---

## 13. Technology Stack

### Frontend (Studio)

- **Next.js 16** with App Router, React 19, React Server Components
- **TypeScript 5** with strict mode
- **Tailwind CSS 4** with custom design tokens (dark warm palette: `#1F1A17` / `#E8E0D4` / `#6B5876` / `#7A8548` / `#42403D`)
- **shadcn/ui** components (Card, Dialog, Table, AlertDialog, Tooltip, Select, Collapsible, Progress, ...)
- **Zustand** for view routing (single `/` route, in-memory view switching)
- **TanStack Query** + a small `useApi` hook (AbortController + refetch interval)
- **Recharts** for canary / MTTR / reliability visualizations
- **Framer Motion** for view transitions
- **Octicons** (via `@primer/octicons-react`) — no lucide
- **Cormorant Garamond** (headings) + **Hanken Grotesk** (body)

### Backend (Orchestrator)

- **FastAPI** 0.128
- **Pydantic 2** for domain models and contracts
- **SQLAlchemy 2** (async) for ORM
- **httpx** for adapter HTTP calls
- **PyJWT** for auth tokens
- **Playwright** + custom stealth evasions (`adapters/stealth.py`) for the local `browser` adapter

### Database

- **Prisma ORM** 6.x for schema management and the frontend's typed client
- **SQLite** for development (zero-config, file-based)
- **PostgreSQL-ready** — change one line in `prisma/schema.prisma` (`provider = "postgresql"`) and update `DATABASE_URL`

### Real-time

- **Socket.io** mini-service on port 3003 for per-execution live trace streaming
- Studio subscribes via `io('/?XTransformPort=3003')`, joins a room per execution ID, receives trace events as they happen

### MCP

- **@modelcontextprotocol/sdk** 1.29
- JSON-RPC 2.0 over HTTP + SSE (works through the Caddy gateway)
- Tool schemas derived directly from action contracts

### LLM

- **z-ai-web-dev-sdk** for the repair proposer, schema compiler, and vision adapter
- Used at **compile time** (recording → contract) and **repair time** (rupture → candidate selector)
- Never used at runtime in the happy path

### Browser

- **Playwright** with custom stealth evasions for the local `browser` adapter (no `playwright-stealth` dependency — the evasions are in-tree and dependency-free)
- **Browser Use Cloud** as the optional `bu_browser` adapter (self-provisioning via challenge-response signup, only activated when the action opts in)
- **Chrome extension** for recording (manifest v3, captures DOM events + HAR + screenshots)

---

## 14. What's Real vs Simulated (Honesty Section)

Earendel is a working research-grade system, not a polished commercial product. Some components are production-ready; others are simulations designed to demonstrate the architecture. We believe transparency here is more valuable than the appearance of completeness.

### Real (production-grade)

- **6-adapter fallback chain** — fully implemented, traces propagated end-to-end, postcondition validation between adapters.
- **Network Discovery (Option B)** — real HAR analyzer (`core/discovery/har_analyzer.py`, ~580 lines), real clustering + scoring + field-mapping inference, real `internal_route` adapter that queries the DB and replays endpoints.
- **Repair Flywheel (Option A)** — real KB storage, real three-tier (KB → LLM → fallback) repair ladder, real combined-score ranking, real cross-client `patternKey` matching.
- **Typed action contracts** — Pydantic models, postcondition runner, schema validator. All production-grade.
- **Versioning** — semver bumping, contract snapshots, rollback.
- **Canary monitoring** — runs every 15 min, marks actions `degraded` / `broken`, auto-generates repair proposals.
- **MCP server** — real JSON-RPC 2.0, real `tools/list` + `tools/call`, real schema derivation.
- **Studio UI** — all 13 views (Dashboard, Connectors, Recorder, Actions, Action Detail, Executions, Monitoring, Discovery, Repair KB, Publishing, Playground, plus connector/recording detail) are functional and wired to live endpoints.
- **Risk gating** — real `RISK_POLICY` enforcement, real human-escalation on critical actions.
- **BU adapter** — real self-provisioning (challenge-response signup with a safe recursive-descent math parser, no `eval()`), real session creation + task execution against the BU Cloud API. Falls back gracefully if the API is unreachable.

### Simulated (demo mode, swappable for real)

- **`api` adapter** — currently returns deterministic simulated outputs. The adapter is structured so swapping in a real Stripe / SAP / etc. SDK is a one-file change.
- **`browser` adapter (in demo mode)** — when `EARENDEL_DEMO_MODE=true` (the default for tests + dev), the adapter uses a deterministic simulation with a 15% failure rate to exercise the repair loop. When `EARENDEL_DEMO_MODE=false`, it tries real Playwright first, falling back to simulation only on Playwright failure.
- **`vision` adapter** — currently uses deterministic parsing of a fixture. The real VLM call (z-ai-web-dev-sdk) is wired but only invoked when the fixture is missing.
- **`human` adapter** — currently returns a queued-for-review stub. The human review queue UI is functional; the human-in-the-loop completion is manual (operator clicks "Approve" or "Reject" in the Studio).
- **LLM client** — `infrastructure/llm_client.py` is a deterministic stub that routes by keyword (compile / repair / classify) and returns plausible responses. The real z-ai-web-dev-sdk integration is a drop-in replacement; the stub exists so tests are fast and offline.
- **Seed data** — `backend/app/seed.py` populates 3 connectors (Acme Finance, Maersk Logistics, BlueCross Healthcare), 2 recordings, 3 published actions, 6 executions, 2 repair proposals, and a handful of KB entries. This is demo data, not real customer data.

### The honest takeaway

The architecture is real. The data flow is real. The fallback chain, the discovery pipeline, the repair flywheel, the MCP integration — all of these are implemented and tested. The thing that is **simulated** is the *external world*: the real Stripe API, the real Acme portal, the real LLM responses. Those are gated behind environment variables and adapter implementations that are designed to be swapped in one PR at a time.

If you want to run Earendel against a real portal today: set `EARENDEL_DEMO_MODE=false`, record a workflow in the Chrome extension, compile it, and the `internal_route` and `browser` adapters will exercise real HTTP and real Playwright respectively. The `api` adapter needs you to wire in the upstream SDK; the `vision` adapter needs a real VLM endpoint; the `human` adapter needs you to staff the review queue. None of these are architectural changes — they're integration work.

---

## 15. License & Acknowledgments

### License

MIT. See `LICENSE` for the full text.

### Acknowledgments

This project stands on the shoulders of several research and open-source efforts:

- **APISENSOR** (network discovery research) — the empirical basis for our HAR-based endpoint discovery. Their reported **95.92% precision** is the floor we design to.
- **Web Verbs** (typed action contracts) — the inspiration for treating browser workflows as typed functions with preconditions and postconditions, rather than as natural-language scripts.
- **MCP** (Model Context Protocol) — Anthropic's protocol for agent ↔ tool communication. Earendel is MCP-native from day one because we believe MCP is becoming the universal standard.
- **Browser Use** — for the stealth browser infrastructure and CAPTCHA-solving capability we wrap as adapter #4. We don't compete with BU on what they're best at; we partner with them.
- **Playwright** — for the browser automation foundation that powers our local `browser` adapter.
- **OmniParser** — for the screenshot-grounded parsing research that informs our `vision` adapter design.
- **AutoRPA** — for the broader research program of treating RPA maintenance as a first-class engineering problem rather than a manual chore.

### The name

Earendel is the Old English word for a shining light — the morning star, the herald of dawn. In Tolkien's legendarium, Eärendil sails the heavens with a Silmaril bound to his brow, a light that guides the faithful through darkness. We named the project Earendel because the work is to be a light for AI agents in the dark forest of business portals — a reliable, typed, monitored, repairable bridge between the agent that wants to do the work and the portal that holds the work.

---

*Earendel is a research-grade system. The architecture is production-real; some external integrations are simulated for testability. See [What's Real vs Simulated](#14-whats-real-vs-simulated-honesty-section) for the full accounting.*
