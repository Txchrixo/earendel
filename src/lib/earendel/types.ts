// Earendel shared domain types — mirror the FastAPI core domain models.
// Source of truth for the frontend; kept in sync with backend/app/core/domain.

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type AdapterType =
  | "api"
  | "internal_route"
  | "browser"
  | "vision"
  | "human";
export type ActionStatus = "draft" | "testing" | "published" | "degraded" | "broken";
export type ExecutionStatus =
  | "queued"
  | "running"
  | "success"
  | "failed"
  | "degraded"
  | "human_review";
export type PermissionScope = "read_only" | "read_write" | "submit" | "destructive";
export type WorkflowCategory =
  | "finance"
  | "healthcare"
  | "logistics"
  | "ecommerce"
  | "hr"
  | "compliance"
  | "government"
  | "other";

export interface FieldSchema {
  name: string;
  type: "string" | "number" | "boolean" | "date" | "url" | "enum" | "file";
  required: boolean;
  description?: string;
  enum?: string[];
  default?: string | number | boolean | null;
}

export interface ActionContract {
  inputs: FieldSchema[];
  outputs: FieldSchema[];
  preconditions: string[];
  postconditions: string[];
}

export interface Connector {
  id: string;
  name: string;
  targetApp: string;
  targetDomain: string;
  workflow: string;
  category: WorkflowCategory;
  permission: PermissionScope;
  riskLevel: RiskLevel;
  allowedDomains: string[];
  authMethod: "password" | "sso" | "api_key" | "oauth";
  status: "active" | "paused" | "error";
  credentialVaultKey: string;
  createdAt: string;
  updatedAt: string;
}

export interface CapturedStep {
  index: number;
  type: "navigate" | "click" | "input" | "select" | "download" | "wait" | "assert";
  description: string;
  selector?: string;
  url?: string;
  value?: string;
  networkCalls?: number;
  screenshot?: boolean;
  durationMs: number;
}

export interface Recording {
  id: string;
  connectorId: string;
  name: string;
  steps: CapturedStep[];
  totalDurationMs: number;
  networkRequests: number;
  domMutations: number;
  screenshots: number;
  harCaptured: boolean;
  status: "captured" | "compiling" | "compiled" | "failed";
  compiledActionId?: string;
  createdAt: string;
}

export interface ActionVersion {
  version: string;
  releasedAt: string;
  changelog: string;
  adapter: AdapterType;
  successRate: number;
  status: "stable" | "latest" | "deprecated" | "rollback";
  contractSnapshot?: ActionContract;
}

export interface CanaryTest {
  id: string;
  actionId: string;
  name: string;
  schedule: string;
  lastRun: string;
  lastStatus: "passed" | "failed" | "warning";
  passRate: number;
  assertions: { name: string; passed: boolean }[];
}

export interface RepairProposal {
  id: string;
  actionId: string;
  actionVersion: string;
  failedSelector: string;
  candidateSelector: string;
  candidateLabel: string;
  confidence: number;
  reason: string;
  status: "pending" | "approved" | "rejected" | "auto_applied";
  detectedAt: string;
}

export interface TypedAction {
  id: string;
  connectorId: string;
  name: string;
  signature: string;
  description: string;
  category: WorkflowCategory;
  contract: ActionContract;
  permissions: PermissionScope;
  riskLevel: RiskLevel;
  executionMethods: AdapterType[];
  preferredAdapter: AdapterType;
  status: ActionStatus;
  version: string;
  versions: ActionVersion[];
  testsPassed: number;
  testsTotal: number;
  canary: CanaryTest[];
  publishedAs: ("mcp" | "rest" | "sdk" | "webhook")[];
  mcpToolName?: string;
  createdAt: string;
  updatedAt: string;
}

export interface TraceEvent {
  ts: string;
  adapter: AdapterType;
  level: "info" | "warn" | "error";
  message: string;
  step?: string;
  durationMs?: number;
}

export interface Execution {
  id: string;
  actionId: string;
  actionName: string;
  caller: "agent" | "schedule" | "manual" | "canary";
  inputs: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  adapter: AdapterType;
  fallbackChain: AdapterType[];
  status: ExecutionStatus;
  durationMs: number;
  startedAt: string;
  finishedAt?: string;
  traces: TraceEvent[];
  screenshots?: string[];
  postconditionsMet?: boolean;
  errorMessage?: string;
  riskApproved: boolean;
}

export interface MonitoringSummary {
  totalActions: number;
  healthy: number;
  degraded: number;
  broken: number;
  canaryPassRate: number;
  openRepairs: number;
  executions24h: number;
  successRate24h: number;
  mttrHours: number;
}

export interface McpToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, unknown>;
    required: string[];
  };
  outputSchema?: {
    type: "object";
    properties: Record<string, unknown>;
  };
}

export interface PublishedTool {
  actionId: string;
  actionName: string;
  mcpToolName: string;
  restEndpoint: string;
  sdkSnippet: string;
  mcpDefinition: McpToolDefinition;
  webhookUrl: string;
}

export interface McpRegistryEntry {
  actionId: string;
  name: string;
  description: string;
  category: string;
  version: string;
  riskLevel: string;
  mcpToolName: string;
}

export interface McpRegistry {
  serverName: string;
  serverVersion: string;
  protocolVersion: string;
  tools: McpToolDefinition[];
  registry: McpRegistryEntry[];
  claudeConfig: string;
  cursorConfig: string;
  curlInstall: string;
}

export interface TimeSeriesPoint {
  ts: string;
  hourLabel: string;
  successRate: number;
  total: number;
  successes: number;
  failures: number;
}

export interface TimeSeries {
  points: TimeSeriesPoint[];
  hours: number;
  generatedAt: string;
}

export interface SearchActionHit {
  id: string;
  name: string;
  signature: string;
  description: string;
  category: string;
  status: string;
  version: string;
}

export interface SearchConnectorHit {
  id: string;
  name: string;
  targetApp: string;
  targetDomain: string;
  category: string;
  status: string;
}

export interface SearchExecutionHit {
  id: string;
  actionId: string;
  actionName: string;
  status: string;
  adapter: string;
  caller: string;
  durationMs: number;
}

export interface SearchRecordingHit {
  id: string;
  name: string;
  connectorId: string;
  status: string;
  steps: number;
}

export interface SearchRepairHit {
  id: string;
  actionId: string;
  actionVersion: string;
  status: string;
  confidence: number;
  candidateSelector: string;
  reason: string;
}

export interface SearchResults {
  actions: SearchActionHit[];
  connectors: SearchConnectorHit[];
  executions: SearchExecutionHit[];
  recordings: SearchRecordingHit[];
  repairs: SearchRepairHit[];
}

export interface ActivityEvent {
  type: "execution" | "repair" | "recording" | "version";
  ts: string;
  title: string;
  description: string;
  refId: string;
  refType: "execution" | "repair" | "recording" | "action";
  status: string;
}

export interface ActivityFeed {
  events: ActivityEvent[];
  total: number;
}

export interface DashboardStats {
  connectors: number;
  recordings: number;
  publishedActions: number;
  executionsToday: number;
  successRate: number;
  openRepairs: number;
  canaryCoverage: number;
}

export type StudioView =
  | "dashboard"
  | "connectors"
  | "connector-detail"
  | "recorder"
  | "actions"
  | "action-detail"
  | "executions"
  | "monitoring"
  | "publishing"
  | "playground";
