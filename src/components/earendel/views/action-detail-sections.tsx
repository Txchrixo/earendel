"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { Icon, type ErIconName } from "../icon";
import { useApi } from "../use-api";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import type {
  TypedAction,
  FieldSchema,
  AdapterType,
  Execution,
  ActionVersion,
} from "@/lib/earendel/types";
import {
  StatusDot,
  AdapterChip,
  RiskBadge,
  CodeBlock,
  EmptyState,
} from "../primitives";

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

const ADAPTER_META: Record<
  AdapterType,
  { icon: ErIconName; name: string; desc: string; reliability: string; speed: string }
> = {
  api: {
    icon: "server",
    name: "Official API",
    desc: "First-party REST call against the vendor's published API.",
    reliability: "99%",
    speed: "~120ms",
  },
  internal_route: {
    icon: "link",
    name: "Internal route",
    desc: "Discovered internal endpoint reached via session cookies.",
    reliability: "94%",
    speed: "~180ms",
  },
  browser: {
    icon: "browser",
    name: "Browser automation",
    desc: "Headless browser replays the recorded click-flow.",
    reliability: "80%",
    speed: "~900ms",
  },
  vision: {
    icon: "eye",
    name: "Vision (OmniParser)",
    desc: "Grounded visual parsing when DOM selectors drift.",
    reliability: "70%",
    speed: "~1400ms",
  },
  human: {
    icon: "person",
    name: "Human review",
    desc: "Escalated to a human operator for authorisation.",
    reliability: "100%",
    speed: "minutes",
  },
};

const FALLBACK_ORDER: AdapterType[] = [
  "api",
  "internal_route",
  "browser",
  "vision",
  "human",
];

function tsType(f: FieldSchema): string {
  switch (f.type) {
    case "string":
      return "string";
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "date":
      return "string /* ISO date */";
    case "url":
      return "string /* URL */";
    case "file":
      return "Blob";
    case "enum":
      return f.enum && f.enum.length
        ? f.enum.map((e) => `"${e}"`).join(" | ")
        : "string";
    default:
      return "string";
  }
}

function tsSignature(action: TypedAction): string {
  const params = action.contract.inputs
    .map((i) => `${i.name}${i.required ? "" : "?"}: ${tsType(i)}`)
    .join(", ");
  const out = action.contract.outputs
    .map((o) => `  ${o.name}: ${tsType(o)};`)
    .join("\n");
  return `async function ${action.name}(${params}): Promise<{\n${out}\n}>`;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/* ------------------------------------------------------------------ */
/* Contract tab                                                       */
/* ------------------------------------------------------------------ */

function FieldList({ title, fields }: { title: string; fields: FieldSchema[] }) {
  return (
    <Card className="gap-3 p-4">
      <div className="flex items-center gap-2">
        <Icon name={title === "Inputs" ? "arrowDown" : "arrowRight"} size={14} aria-hidden />
        <h4 className="er-h3">{title}</h4>
        <Badge variant="secondary" className="ml-auto">
          {fields.length}
        </Badge>
      </div>
      <ul className="divide-y divide-border">
        {fields.map((f) => (
          <li key={f.name} className="py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <code className="font-mono text-sm text-foreground">{f.name}</code>
              <Badge variant="outline" className="er-caption">
                {f.type}
              </Badge>
              {f.required && (
                <span className="er-caption text-destructive">*</span>
              )}
            </div>
            {f.description && (
              <p className="er-caption mt-1 text-muted-foreground">{f.description}</p>
            )}
            {f.enum && f.enum.length > 0 && (
              <p className="er-caption mt-1 font-mono text-muted-foreground">
                enum: {f.enum.join(" | ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Checklist({
  title,
  items,
  icon,
}: {
  title: string;
  items: string[];
  icon: ErIconName;
}) {
  return (
    <Card className="gap-2 p-4">
      <div className="flex items-center gap-2">
        <Icon name={icon} size={14} aria-hidden />
        <h4 className="text-sm font-medium">{title}</h4>
      </div>
      <ul className="space-y-1.5">
        {items.length === 0 && (
          <li className="er-caption text-muted-foreground">None declared.</li>
        )}
        {items.map((c, i) => (
          <li key={i} className="flex items-start gap-2 er-caption">
            <Icon
              name={icon === "shieldCheck" ? "check" : "tasklist"}
              size={12}
              className="mt-0.5 shrink-0 text-accent"
              aria-hidden
            />
            <span className="text-muted-foreground">{c}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function ContractTab({ action }: { action: TypedAction }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <CodeBlock code={tsSignature(action)} language="typescript" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FieldList title="Inputs" fields={action.contract.inputs} />
        <FieldList title="Outputs" fields={action.contract.outputs} />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Checklist
          title="Preconditions"
          items={action.contract.preconditions}
          icon="shieldCheck"
        />
        <Checklist
          title="Postconditions"
          items={action.contract.postconditions}
          icon="tasklist"
        />
      </div>
      <Card className="gap-2 p-4">
        <div className="flex items-center gap-2">
          <Icon name="lock" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Permission & risk</h4>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="secondary" className="gap-1">
            <Icon name="key" size={12} aria-hidden /> {action.permissions}
          </Badge>
          <RiskBadge level={action.riskLevel} />
          <span className="er-caption text-muted-foreground">
            Read-only flows run automatically; destructive flows require human
            authorisation before each run.
          </span>
        </div>
      </Card>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Execution tab — fallback chain stepper                             */
/* ------------------------------------------------------------------ */

export function ExecutionTab({ action }: { action: TypedAction }) {
  const active = new Set<AdapterType>(action.executionMethods);
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <ol className="relative flex flex-col gap-2">
        {FALLBACK_ORDER.map((adapter, i) => {
          const meta = ADAPTER_META[adapter];
          const isActive = active.has(adapter);
          const isPreferred = action.preferredAdapter === adapter;
          return (
            <li key={adapter} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    "grid size-9 place-items-center rounded-md border",
                    isActive
                      ? "border-accent bg-accent/15 text-accent"
                      : "border-border bg-secondary text-muted-foreground",
                  )}
                >
                  <Icon name={meta.icon} size={16} aria-hidden />
                </span>
                {i < FALLBACK_ORDER.length - 1 && (
                  <span className="my-1 h-full w-px flex-1 bg-border" aria-hidden />
                )}
              </div>
              <Card
                className={cn(
                  "flex-1 gap-1 p-3",
                  !isActive && "opacity-60",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{meta.name}</span>
                  <Badge variant="outline" className="er-caption">
                    step {i + 1}
                  </Badge>
                  {isPreferred && (
                    <Badge className="bg-accent text-accent-foreground">
                      <Icon name="star" size={10} aria-hidden /> Preferred
                    </Badge>
                  )}
                  {!isActive && (
                    <span className="er-caption text-muted-foreground">inactive</span>
                  )}
                </div>
                <p className="er-caption text-muted-foreground">{meta.desc}</p>
                <div className="mt-1 flex flex-wrap gap-3 er-caption text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Icon name="shieldCheck" size={11} aria-hidden /> {meta.reliability}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Icon name="clock" size={11} aria-hidden /> {meta.speed}
                  </span>
                </div>
              </Card>
            </li>
          );
        })}
      </ol>
      <Card className="gap-2 border-chart-4/30 bg-chart-4/5 p-4">
        <div className="flex items-center gap-2">
          <Icon name="shield" size={14} className="text-chart-4" aria-hidden />
          <h4 className="text-sm font-medium">Risk-gating policy</h4>
        </div>
        <p className="er-caption text-muted-foreground">
          Read-only flows execute through the chain automatically. Destructive
          and submit-level permissions pause before the final step and require a
          human authorisation token — surfaced in the Executions view as
          <span className="text-foreground"> human_review</span>.
        </p>
      </Card>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Tests & Canary tab                                                 */
/* ------------------------------------------------------------------ */

export function TestsCanaryTab({ action }: { action: TypedAction }) {
  const { refetch } = useApi(() => Promise.resolve(action), [action.id]);
  const [runningId, setRunningId] = React.useState<string | null>(null);
  const passPct = action.testsTotal > 0 ? (action.testsPassed / action.testsTotal) * 100 : 0;

  const runCanary = async (canaryId: string) => {
    setRunningId(canaryId);
    try {
      await api.runCanary(action.id);
      toast.success("Canary queued", {
        description: "Synthetic run dispatched. Results land in Monitoring.",
      });
      refetch();
    } catch {
      toast.error("Could not run canary", { description: "Backend unreachable." });
    } finally {
      setRunningId(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-3 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="checkCircle" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Test suite</h4>
          </div>
          <span className="er-caption text-muted-foreground">
            {action.testsPassed}/{action.testsTotal} passing
          </span>
        </div>
        <Progress value={passPct} className="bg-secondary" />
      </Card>

      {action.canary.length === 0 ? (
        <EmptyState
          icon="beaker"
          title="No canaries configured"
          description="Schedule a synthetic run to validate this action continuously."
        />
      ) : (
        <div className="grid gap-3">
          {action.canary.map((c) => (
            <Card key={c.id} className="gap-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Icon name="beaker" size={14} className="text-accent" aria-hidden />
                  <span className="text-sm font-medium">{c.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="er-caption text-muted-foreground">
                    <Icon name="calendar" size={11} className="mr-1 inline" aria-hidden />
                    {c.schedule}
                  </span>
                  <StatusDot
                    status={
                      c.lastStatus === "passed"
                        ? "success"
                        : c.lastStatus === "warning"
                          ? "human_review"
                          : "failed"
                    }
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => runCanary(c.id)}
                    disabled={runningId === c.id}
                  >
                    <Icon name="sync" size={12} aria-hidden />
                    {runningId === c.id ? "Running…" : "Run canary now"}
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[160px]">
                  <div className="flex items-center justify-between er-caption text-muted-foreground">
                    <span>Pass rate</span>
                    <span>{Math.round(c.passRate * 100)}%</span>
                  </div>
                  <Progress value={c.passRate * 100} className="mt-1 bg-secondary" />
                </div>
                <span className="er-caption text-muted-foreground">
                  last run {timeAgo(c.lastRun)}
                </span>
              </div>
              <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {c.assertions.map((a, idx) => (
                  <li
                    key={idx}
                    className="flex items-center gap-2 rounded-md border border-border bg-secondary/40 px-2 py-1.5"
                  >
                    <Icon
                      name={a.passed ? "checkCircleFill" : "xCircleFill"}
                      size={12}
                      className={a.passed ? "text-accent" : "text-destructive"}
                      aria-hidden
                    />
                    <code className="font-mono text-xs">{a.name}</code>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Versions tab                                                       */
/* ------------------------------------------------------------------ */

const versionBadge: Record<ActionVersion["status"], React.ReactNode> = {
  stable: <Badge variant="secondary">stable</Badge>,
  latest: (
    <Badge className="bg-accent text-accent-foreground">
      <Icon name="star" size={10} aria-hidden /> latest
    </Badge>
  ),
  deprecated: <Badge variant="outline">deprecated</Badge>,
  rollback: <Badge variant="destructive">rolled back</Badge>,
};

export function VersionsTab({ action }: { action: TypedAction }) {
  const [rolling, setRolling] = React.useState<string | null>(null);
  const setView = useStudio((s) => s.setView);

  const rollback = async (version: string) => {
    setRolling(version);
    try {
      await api.rollbackAction(action.id, version);
      toast.success("Rolled back", {
        description: `${action.name} now serves v${version}.`,
      });
      setView("actions");
    } catch {
      toast.error("Rollback failed", { description: "Backend unreachable." });
    } finally {
      setRolling(null);
    }
  };

  const versions = [...action.versions].sort((a, b) =>
    new Date(b.releasedAt).getTime() - new Date(a.releasedAt).getTime(),
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-3"
    >
      {versions.map((v, i) => {
        const isCurrent = v.version === action.version;
        const canRollback = v.status === "stable" && !isCurrent;
        return (
          <Card key={v.version} className={cn("gap-2 p-4", isCurrent && "border-accent")}>
            <div className="flex flex-wrap items-center gap-3">
              <span className="grid size-8 place-items-center rounded-md bg-primary/20 font-mono text-xs text-primary">
                v{v.version}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{v.changelog}</span>
                  {isCurrent && (
                    <Badge className="bg-accent text-accent-foreground">current</Badge>
                  )}
                  {versionBadge[v.status]}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-3 er-caption text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Icon name="calendar" size={11} aria-hidden />{" "}
                    {new Date(v.releasedAt).toLocaleDateString()}
                  </span>
                  <AdapterChip adapter={v.adapter} />
                  <span className="inline-flex items-center gap-1">
                    <Icon name="meter" size={11} aria-hidden />{" "}
                    {Math.round(v.successRate * 100)}% success
                  </span>
                </div>
              </div>
              {canRollback && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => rollback(v.version)}
                  disabled={rolling === v.version}
                >
                  <Icon name="history" size={12} aria-hidden />
                  {rolling === v.version ? "Rolling back…" : "Rollback"}
                </Button>
              )}
            </div>
            {i < versions.length - 1 && <div className="h-px bg-border" aria-hidden />}
          </Card>
        );
      })}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Executions tab — compact recent list                               */
/* ------------------------------------------------------------------ */

export function ExecutionsTab({ actionId }: { actionId: string }) {
  const { data, loading, error } = useApi<Execution[]>(
    () => api.listExecutions(actionId),
    [actionId],
  );
  const openExecution = useStudio((s) => s.openExecution);
  const items = (data ?? []).slice(0, 12);

  if (error) {
    return (
      <EmptyState
        icon="executions"
        title="Backend connecting…"
        description="Recent runs will appear here shortly."
      />
    );
  }
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <EmptyState
        icon="executions"
        title="No executions yet"
        description="Run this action from the Playground to populate the trace."
      />
    );
  }
  return (
    <Card className="gap-0 p-0">
      <ul className="divide-y divide-border">
        {items.map((e) => (
          <li key={e.id}>
            <button
              type="button"
              onClick={() => openExecution(e.id)}
              className="grid w-full grid-cols-[1fr_auto] items-center gap-3 px-4 py-2.5 text-left hover:bg-secondary/50"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <AdapterChip adapter={e.adapter} />
                  <Badge variant="outline" className="er-caption">
                    {e.caller}
                  </Badge>
                </div>
                <div className="mt-0.5 flex items-center gap-2">
                  <StatusDot status={e.status} />
                  <span className="er-caption text-muted-foreground">
                    {e.durationMs}ms · {timeAgo(e.startedAt)}
                  </span>
                </div>
              </div>
              <Icon name="chevronRight" size={16} className="text-muted-foreground" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
