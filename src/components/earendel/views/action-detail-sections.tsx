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
  Connector,
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
  const [compareA, setCompareA] = React.useState<string | null>(null);
  const [compareB, setCompareB] = React.useState<string | null>(null);
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

  const versionA = versions.find((v) => v.version === compareA);
  const versionB = versions.find((v) => v.version === compareB);
  const showDiff = versionA && versionB;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-3"
    >
      {showDiff && (
        <VersionDiffCard a={versionA!} b={versionB!} onClose={() => { setCompareA(null); setCompareB(null); }} />
      )}
      {versions.map((v, i) => {
        const isCurrent = v.version === action.version;
        const canRollback = v.status === "stable" && !isCurrent;
        const isSelectedA = compareA === v.version;
        const isSelectedB = compareB === v.version;
        return (
          <Card
            key={v.version}
            className={cn(
              "gap-2 p-4 transition-colors",
              isCurrent && "border-accent",
              isSelectedA && "ring-1 ring-chart-2",
              isSelectedB && "ring-1 ring-chart-4",
            )}
          >
            <div className="flex flex-wrap items-center gap-3">
              <span
                className="grid size-8 place-items-center rounded-md bg-secondary text-muted-foreground font-mono text-xs font-bold"
              >
                v{v.version}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{v.changelog}</span>
                  {isCurrent && (
                    <Badge className="er-pill-success">current</Badge>
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
              {/* Compare selectors */}
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant={isSelectedA ? "default" : "ghost"}
                  className={isSelectedA ? "bg-chart-2 text-background" : ""}
                  onClick={() => setCompareA(isSelectedA ? null : v.version)}
                  aria-pressed={isSelectedA}
                  title="Set as version A for comparison"
                >
                  A
                </Button>
                <Button
                  size="sm"
                  variant={isSelectedB ? "default" : "ghost"}
                  className={isSelectedB ? "bg-chart-4 text-background" : ""}
                  onClick={() => setCompareB(isSelectedB ? null : v.version)}
                  aria-pressed={isSelectedB}
                  title="Set as version B for comparison"
                >
                  B
                </Button>
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
      {!showDiff && versions.length >= 2 && (
        <p className="er-caption text-muted-foreground text-center pt-2">
          <Icon name="lightbulb" size={12} aria-hidden className="inline mr-1" />
          Pick two versions (A + B) to compare what changed.
        </p>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* VersionDiffCard — diff between two ActionVersions                  */
/* ------------------------------------------------------------------ */

function VersionDiffCard({
  a,
  b,
  onClose,
}: {
  a: ActionVersion;
  b: ActionVersion;
  onClose: () => void;
}) {
  const adapterChanged = a.adapter !== b.adapter;
  const successDelta = b.successRate - a.successRate;
  const successImproved = successDelta > 0;
  const dateDelta =
    (new Date(b.releasedAt).getTime() - new Date(a.releasedAt).getTime()) / 86400000;

  return (
    <Card className="gap-3 p-5 border-accent/40">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground"
          >
            <Icon name="diff" size={16} aria-hidden />
          </span>
          <div>
            <h4 className="text-sm font-medium">Version comparison</h4>
            <p className="er-caption text-muted-foreground">
              v{a.version} → v{b.version}
            </p>
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close comparison">
          <Icon name="x" size={14} aria-hidden />
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {/* Changelog diff */}
        <div className="w-full rounded-md border border-border bg-background/40 p-3">
          <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1.5">
            Changelog
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <p className="er-caption text-chart-2 mb-0.5">v{a.version}</p>
              <p className="text-sm text-foreground">{a.changelog}</p>
            </div>
            <div>
              <p className="er-caption text-chart-4 mb-0.5">v{b.version}</p>
              <p className="text-sm text-foreground">{b.changelog}</p>
            </div>
          </div>
        </div>

        {/* Metrics diff */}
        <div
          className={cn(
            "rounded-md border px-3 py-2 text-xs",
            adapterChanged ? "er-pill-warn border-transparent" : "border-border bg-secondary text-muted-foreground",
          )}
        >
          <span className="text-muted-foreground">adapter: </span>
          {adapterChanged ? (
            <span className="font-mono">
              <span className="text-chart-2">{a.adapter.replace("_", " ")}</span>
              <Icon name="arrowRight" size={10} className="mx-1 inline" aria-hidden />
              <span className="text-chart-4">{b.adapter.replace("_", " ")}</span>
            </span>
          ) : (
            <span className="font-mono text-foreground">{a.adapter.replace("_", " ")}</span>
          )}
        </div>

        <div
          className={cn(
            "rounded-md border px-3 py-2 text-xs",
            Math.abs(successDelta) > 0.01
              ? successImproved ? "er-pill-success border-transparent" : "er-pill-danger border-transparent"
              : "border-border bg-secondary text-muted-foreground",
          )}
        >
          <span className="text-muted-foreground">success rate: </span>
          <span className="font-mono text-foreground">
            {Math.round(a.successRate * 100)}%
            <Icon name="arrowRight" size={10} className="mx-1 inline" aria-hidden />
            {Math.round(b.successRate * 100)}%
            {Math.abs(successDelta) > 0.01 && (
              <span className={successImproved ? "text-accent" : "text-destructive"}>
                {" "}({successImproved ? "+" : ""}{Math.round(successDelta * 100)}%)
              </span>
            )}
          </span>
        </div>

        <div className="rounded-md border border-border bg-secondary px-3 py-2 text-xs text-muted-foreground">
          <span>released: </span>
          <span className="font-mono text-foreground">
            {new Date(a.releasedAt).toLocaleDateString()}
            <Icon name="arrowRight" size={10} className="mx-1 inline" aria-hidden />
            {new Date(b.releasedAt).toLocaleDateString()}
            {Math.abs(dateDelta) >= 1 && (
              <span className="text-muted-foreground"> ({dateDelta >= 0 ? "+" : ""}{Math.round(dateDelta)}d)</span>
            )}
          </span>
        </div>
      </div>

      {/* Contract diff (inputs/outputs) */}
      {a.contractSnapshot && b.contractSnapshot && (
        <ContractDiff a={a.contractSnapshot} b={b.contractSnapshot} />
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* ContractDiff — inputs/outputs field diff between two contracts      */
/* ------------------------------------------------------------------ */

function fieldKey(f: { name: string }): string {
  return f.name;
}

function ContractDiff({
  a,
  b,
}: {
  a: import("@/lib/earendel/types").ActionContract;
  b: import("@/lib/earendel/types").ActionContract;
}) {
  const aInputs = new Map(a.inputs.map((f) => [fieldKey(f), f]));
  const bInputs = new Map(b.inputs.map((f) => [fieldKey(f), f]));
  const aOutputs = new Map(a.outputs.map((f) => [fieldKey(f), f]));
  const bOutputs = new Map(b.outputs.map((f) => [fieldKey(f), f]));

  const inputAdded = b.inputs.filter((f) => !aInputs.has(fieldKey(f)));
  const inputRemoved = a.inputs.filter((f) => !bInputs.has(fieldKey(f)));
  const outputAdded = b.outputs.filter((f) => !aOutputs.has(fieldKey(f)));
  const outputRemoved = a.outputs.filter((f) => !bOutputs.has(fieldKey(f)));

  const hasChanges =
    inputAdded.length > 0 ||
    inputRemoved.length > 0 ||
    outputAdded.length > 0 ||
    outputRemoved.length > 0;

  if (!hasChanges) return null;

  return (
    <div className="w-full rounded-md border border-border bg-background/40 p-3">
      <p className="er-caption text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <Icon name="diff" size={11} aria-hidden /> Contract diff
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Inputs diff */}
        <div>
          <p className="er-caption text-muted-foreground mb-1">Inputs</p>
          {inputAdded.length === 0 && inputRemoved.length === 0 ? (
            <p className="er-caption text-muted-foreground/60">unchanged</p>
          ) : (
            <div className="flex flex-col gap-1">
              {inputAdded.map((f) => (
                <div key={`+i${f.name}`} className="flex items-center gap-1.5 er-pill-success rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">+</span>
                  <code className="font-mono">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
              {inputRemoved.map((f) => (
                <div key={`-i${f.name}`} className="flex items-center gap-1.5 er-pill-danger rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">−</span>
                  <code className="font-mono line-through">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {/* Outputs diff */}
        <div>
          <p className="er-caption text-muted-foreground mb-1">Outputs</p>
          {outputAdded.length === 0 && outputRemoved.length === 0 ? (
            <p className="er-caption text-muted-foreground/60">unchanged</p>
          ) : (
            <div className="flex flex-col gap-1">
              {outputAdded.map((f) => (
                <div key={`+o${f.name}`} className="flex items-center gap-1.5 er-pill-success rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">+</span>
                  <code className="font-mono">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
              {outputRemoved.map((f) => (
                <div key={`-o${f.name}`} className="flex items-center gap-1.5 er-pill-danger rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">−</span>
                  <code className="font-mono line-through">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
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

/* ------------------------------------------------------------------ */
/* Dependencies tab — connector, credentials, adapters, permissions    */
/* ------------------------------------------------------------------ */

export function DependenciesTab({ action }: { action: TypedAction }) {
  const openConnector = useStudio((s) => s.openConnector);
  const setView = useStudio((s) => s.setView);
  const { data: connector, loading: connLoading, error: connError } = useApi<Connector>(
    () => api.getConnector(action.connectorId),
    [action.connectorId],
  );

  const adapterChain = action.executionMethods;
  const fallbackDepth = adapterChain.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      {/* Connector dependency */}
      <Card className="gap-3 p-5">
        <div className="flex items-center gap-2">
          <Icon name="connectors" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Connector</h4>
        </div>
        {connError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3">
            <p className="er-caption text-destructive flex items-center gap-1.5">
              <Icon name="alertFill" size={11} aria-hidden /> Connector not found
            </p>
            <p className="er-caption text-muted-foreground mt-1">
              The connector{" "}
              <code className="font-mono text-foreground">{action.connectorId}</code>{" "}
              may have been deleted. The action is orphaned.
            </p>
          </div>
        ) : connLoading ? (
          <p className="er-caption text-muted-foreground flex items-center gap-1.5">
            <Icon name="sync" size={12} className="er-pulse" aria-hidden /> Loading connector…
          </p>
        ) : connector ? (
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="grid size-9 place-items-center rounded-md bg-primary text-primary-foreground"
            >
              <Icon name="globe" size={16} aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">{connector.name}</p>
              <p className="er-caption text-muted-foreground font-mono">{connector.targetDomain}</p>
            </div>
            <Badge className="er-pill-neutral capitalize">{connector.authMethod}</Badge>
            <RiskBadge level={connector.riskLevel} />
            <Button size="sm" variant="outline" onClick={() => openConnector(connector.id)}>
              <Icon name="eye" size={12} aria-hidden /> View
            </Button>
          </div>
        ) : (
          <p className="er-caption text-muted-foreground">Loading connector…</p>
        )}
      </Card>

      {/* Credential vault */}
      {connector && (
        <Card className="gap-3 p-5">
          <div className="flex items-center gap-2">
            <Icon name="lock" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Credential vault</h4>
          </div>
          <div className="rounded-md border border-border bg-background/40 p-3">
            <div className="flex items-center justify-between">
              <code className="font-mono text-xs text-muted-foreground">
                {connector.credentialVaultKey}
              </code>
              <Badge className="er-pill-success">
                <Icon name="shieldCheck" size={10} aria-hidden /> sealed
              </Badge>
            </div>
            <p className="er-caption text-muted-foreground mt-2">
              Credentials are fetched at runtime through the vault — never embedded in LLM
              prompts or logs. RBAC scopes this action to{" "}
              <span className="text-foreground font-medium capitalize">
                {action.permissions.replace("_", " ")}
              </span>{" "}
              operations.
            </p>
          </div>
        </Card>
      )}

      {/* Adapter chain */}
      <Card className="gap-3 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="iterations" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Execution adapters</h4>
          </div>
          <span className="er-caption text-muted-foreground">
            fallback depth {fallbackDepth}
          </span>
        </div>
        <div className="flex flex-col gap-2">
          {adapterChain.map((adapter, i) => {
            const isPreferred = adapter === action.preferredAdapter;
            return (
              <div
                key={adapter}
                className={cn(
                  "flex items-center gap-3 rounded-md border px-3 py-2",
                  isPreferred ? "border-accent/40 bg-accent/5" : "border-border bg-secondary/40",
                )}
              >
                <span className="er-caption text-muted-foreground w-6 text-center font-mono">
                  {i + 1}
                </span>
                <AdapterChip adapter={adapter} active={isPreferred} />
                <span className="text-sm text-muted-foreground flex-1">
                  {isPreferred ? "Preferred — tried first" : "Fallback — tried if preferred fails"}
                </span>
                {isPreferred && (
                  <Badge className="er-pill-success text-xs">preferred</Badge>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Permission + risk summary */}
      <Card className="gap-3 p-5">
        <div className="flex items-center gap-2">
          <Icon name="shield" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Permission & risk</h4>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1">
              Permission scope
            </p>
            <p className="text-sm font-medium capitalize text-foreground">
              {action.permissions.replace("_", " ")}
            </p>
            <p className="er-caption text-muted-foreground mt-1">
              {action.permissions === "read_only"
                ? "Auto-run enabled — no human approval needed."
                : action.permissions === "read_write"
                  ? "Auto-run + log — mutations logged."
                  : action.permissions === "submit"
                    ? "Human confirmation required before submit."
                    : "Strict approval — typed confirmation required."}
            </p>
          </div>
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1">
              Risk level
            </p>
            <div className="flex items-center gap-2">
              <RiskBadge level={action.riskLevel} />
            </div>
            <p className="er-caption text-muted-foreground mt-1">
              {action.riskLevel === "low"
                ? "Read-only data retrieval — safe to auto-run."
                : action.riskLevel === "medium"
                  ? "May mutate state — logged + monitored."
                  : action.riskLevel === "high"
                    ? "Consequential — human authorisation required."
                    : "Destructive — strict typed confirmation."}
            </p>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
