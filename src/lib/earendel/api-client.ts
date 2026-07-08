// Earendel API client — talks to the FastAPI modular backend via the Caddy
// gateway using XTransformPort=8001. All requests use relative paths.

import type {
  Connector,
  Recording,
  TypedAction,
  Execution,
  MonitoringSummary,
  PublishedTool,
  McpRegistry,
  TimeSeries,
  DashboardStats,
  RepairProposal,
} from "./types";

const BACKEND_PORT = "8001";

class ApiError extends Error {
  status: number;
  detail?: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { params?: Record<string, string> },
): Promise<T> {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("XTransformPort", BACKEND_PORT);
  if (init?.params) {
    for (const [k, v] of Object.entries(init.params)) url.searchParams.set(k, v);
  }
  const res = await fetch(url.toString(), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(`API ${res.status}`, res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // ---- Dashboard ----
  stats: () => request<DashboardStats>("/api/v1/dashboard/stats"),
  monitoring: () => request<MonitoringSummary>("/api/v1/monitoring/summary"),
  /** Generic raw GET for endpoints with arbitrary response shapes (e.g. /healthz, /readyz). */
  raw: <T,>(path: string) => request<T>(path),

  // ---- Connectors ----
  listConnectors: () => request<Connector[]>("/api/v1/connectors"),
  getConnector: (id: string) => request<Connector>(`/api/v1/connectors/${id}`),
  createConnector: (body: Partial<Connector>) =>
    request<Connector>("/api/v1/connectors", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // ---- Recordings ----
  listRecordings: () => request<Recording[]>("/api/v1/recordings"),
  getRecording: (id: string) => request<Recording>(`/api/v1/recordings/${id}`),
  createRecording: (body: Partial<Recording>) =>
    request<Recording>("/api/v1/recordings", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  compileRecording: (id: string) =>
    request<{ action: TypedAction }>(`/api/v1/recordings/${id}/compile`, {
      method: "POST",
    }),

  // ---- Actions ----
  listActions: (connectorId?: string) =>
    request<TypedAction[]>("/api/v1/actions", {
      params: connectorId ? { connectorId } : undefined,
    }),
  getAction: (id: string) => request<TypedAction>(`/api/v1/actions/${id}`),
  publishAction: (id: string, targets: ("mcp" | "rest" | "sdk" | "webhook")[]) =>
    request<TypedAction>(`/api/v1/actions/${id}/publish`, {
      method: "POST",
      body: JSON.stringify({ targets }),
    }),
  rollbackAction: (id: string, version: string) =>
    request<TypedAction>(`/api/v1/actions/${id}/rollback`, {
      method: "POST",
      body: JSON.stringify({ version }),
    }),

  // ---- Executions ----
  listExecutions: (actionId?: string) =>
    request<Execution[]>("/api/v1/executions", {
      params: actionId ? { actionId } : undefined,
    }),
  getExecution: (id: string) => request<Execution>(`/api/v1/executions/${id}`),
  runAction: (
    actionId: string,
    inputs: Record<string, unknown>,
    caller: "agent" | "manual" = "manual",
  ) =>
    request<Execution>("/api/v1/executions", {
      method: "POST",
      body: JSON.stringify({ actionId, inputs, caller }),
    }),

  // ---- Monitoring ----
  timeseries: (hours: number = 24) =>
    request<TimeSeries>("/api/v1/monitoring/timeseries", {
      params: { hours: String(hours) },
    }),
  listRepairs: (actionId?: string) =>
    request<RepairProposal[]>("/api/v1/monitoring/repairs", {
      params: actionId ? { actionId } : undefined,
    }),
  resolveRepair: (id: string, decision: "approved" | "rejected") =>
    request<RepairProposal>(`/api/v1/monitoring/repairs/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  runCanary: (actionId: string) =>
    request<{ status: string }>("/api/v1/monitoring/canary/run", {
      method: "POST",
      body: JSON.stringify({ actionId }),
    }),
  proposeRepair: (actionId: string, executionId: string) =>
    request<RepairProposal | { proposal: null }>(
      "/api/v1/monitoring/repairs/propose",
      { method: "POST", body: JSON.stringify({ actionId, executionId }) },
    ),

  // ---- Publishing ----
  getPublishedTool: (actionId: string) =>
    request<PublishedTool>(`/api/v1/publishing/${actionId}`),
  getMcpRegistry: () =>
    request<McpRegistry>("/api/v1/publishing/registry"),
};

export { ApiError };
