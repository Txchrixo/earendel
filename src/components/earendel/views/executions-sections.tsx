"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import type {
  Execution,
  ExecutionStatus,
  AdapterType,
  TraceEvent,
} from "@/lib/earendel/types";
import {
  StatusDot,
  AdapterChip,
  EmptyState,
  CodeBlock,
} from "../primitives";

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    month: "short",
    day: "numeric",
  });
}

/* ------------------------------------------------------------------ */
/* List view                                                          */
/* ------------------------------------------------------------------ */

const STATUS_OPTIONS: ExecutionStatus[] = [
  "success",
  "failed",
  "degraded",
  "human_review",
  "running",
];
const CALLER_OPTIONS = ["agent", "schedule", "manual", "canary"] as const;
const ADAPTER_OPTIONS: AdapterType[] = [
  "api",
  "internal_route",
  "browser",
  "vision",
  "human",
];

export function ExecutionsList() {
  const { data, loading, error } = useApi<Execution[]>(() => api.listExecutions(), []);
  const openExecution = useStudio((s) => s.openExecution);
  const [status, setStatus] = React.useState<ExecutionStatus | "all">("all");
  const [caller, setCaller] = React.useState<(typeof CALLER_OPTIONS)[number] | "all">("all");
  const [adapter, setAdapter] = React.useState<AdapterType | "all">("all");

  const filtered = (data ?? []).filter((e) => {
    if (status !== "all" && e.status !== status) return false;
    if (caller !== "all" && e.caller !== caller) return false;
    if (adapter !== "all" && e.adapter !== adapter) return false;
    return true;
  });

  return (
    <Card className="gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Icon name="filter" size={14} className="text-muted-foreground" aria-hidden />
        <Select value={status} onValueChange={(v) => setStatus(v as ExecutionStatus | "all")}>
          <SelectTrigger size="sm" className="w-32" aria-label="Filter by status">
            <SelectValue placeholder="status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">all statuses</SelectItem>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s} value={s}>
                {s.replace("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={caller} onValueChange={(v) => setCaller(v as typeof caller)}>
          <SelectTrigger size="sm" className="w-32" aria-label="Filter by caller">
            <SelectValue placeholder="caller" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">all callers</SelectItem>
            {CALLER_OPTIONS.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={adapter} onValueChange={(v) => setAdapter(v as AdapterType | "all")}>
          <SelectTrigger size="sm" className="w-40" aria-label="Filter by adapter">
            <SelectValue placeholder="adapter" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">all adapters</SelectItem>
            {ADAPTER_OPTIONS.map((a) => (
              <SelectItem key={a} value={a}>
                {a.replace("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="ml-auto er-caption text-muted-foreground">
          {filtered.length} runs
        </span>
      </div>

      {error ? (
        <EmptyState
          icon="executions"
          spot="executions"
          title="Backend connecting…"
          description="Recent executions will appear here shortly."
        />
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="executions"
          spot="executions"
          title="No executions match"
          description="Adjust the filters or run an action from the Playground."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Action</TableHead>
              <TableHead>Caller</TableHead>
              <TableHead>Adapter</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Post-conditions</TableHead>
              <TableHead>When</TableHead>
              <TableHead className="w-8" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((e) => (
              <TableRow
                key={e.id}
                className="cursor-pointer"
                onClick={() => openExecution(e.id)}
              >
                <TableCell className="font-medium">{e.actionName}</TableCell>
                <TableCell>
                  <Badge variant="outline" className="er-caption">
                    {e.caller}
                  </Badge>
                </TableCell>
                <TableCell>
                  <AdapterChip adapter={e.adapter} />
                </TableCell>
                <TableCell>
                  <StatusDot status={e.status} />
                </TableCell>
                <TableCell className="tabular-nums">{e.durationMs}ms</TableCell>
                <TableCell>
                  {e.postconditionsMet === undefined ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <Icon
                      name={e.postconditionsMet ? "checkCircleFill" : "xCircleFill"}
                      size={14}
                      className={e.postconditionsMet ? "text-accent" : "text-destructive"}
                      aria-label={e.postconditionsMet ? "met" : "not met"}
                    />
                  )}
                </TableCell>
                <TableCell className="er-caption text-muted-foreground">
                  {timeAgo(e.startedAt)}
                </TableCell>
                <TableCell>
                  <Icon
                    name="chevronRight"
                    size={14}
                    className="text-muted-foreground"
                    aria-hidden
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Detail view                                                        */
/* ------------------------------------------------------------------ */

const traceLevelColor: Record<TraceEvent["level"], string> = {
  info: "text-muted-foreground",
  warn: "text-chart-4",
  error: "text-destructive",
};

function TraceTimeline({ traces }: { traces: TraceEvent[] }) {
  return (
    <ol className="relative flex max-h-[28rem] flex-col gap-0 overflow-y-auto er-scroll">
      {traces.map((t, i) => (
        <li key={i} className="relative flex gap-3 pl-2">
          <div className="flex flex-col items-center">
            <span
              className={cn(
                "mt-1.5 size-2.5 rounded-full border-2 border-card",
                t.level === "error"
                  ? "bg-destructive"
                  : t.level === "warn"
                    ? "bg-chart-4"
                    : "bg-primary",
              )}
              aria-hidden
            />
            {i < traces.length - 1 && (
              <span className="my-0.5 w-px flex-1 bg-border" aria-hidden />
            )}
          </div>
          <div className="flex-1 pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="er-caption font-mono text-muted-foreground">
                {new Date(t.ts).toLocaleTimeString(undefined, { hour12: false })}
              </span>
              <AdapterChip adapter={t.adapter} />
              {t.step && (
                <Badge variant="outline" className="er-caption font-mono">
                  {t.step}
                </Badge>
              )}
              {t.durationMs != null && (
                <span className="er-caption tabular-nums text-muted-foreground">
                  {t.durationMs}ms
                </span>
              )}
            </div>
            <p className={cn("mt-0.5 text-sm", traceLevelColor[t.level])}>{t.message}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function FallbackChain({ execution }: { execution: Execution }) {
  const tried = new Set<AdapterType>(execution.fallbackChain);
  const succeeded = execution.adapter;
  return (
    <Card className="gap-2 p-4">
      <div className="flex items-center gap-2">
        <Icon name="iterations" size={14} aria-hidden />
        <h4 className="text-sm font-medium">Fallback chain</h4>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {execution.fallbackChain.map((a, i) => {
          const isSucceeded = a === succeeded;
          return (
            <React.Fragment key={a}>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-2 py-1 er-caption",
                  isSucceeded
                    ? "border-accent bg-accent/15 text-accent"
                    : "border-border bg-secondary text-muted-foreground",
                )}
              >
                <Icon
                  name={isSucceeded ? "checkCircleFill" : "x"}
                  size={11}
                  aria-hidden
                />
                {a.replace("_", " ")}
              </span>
              {i < execution.fallbackChain.length - 1 && (
                <Icon name="arrowRight" size={12} className="text-muted-foreground" aria-hidden />
              )}
            </React.Fragment>
          );
        })}
        {tried.size === 0 && (
          <span className="er-caption text-muted-foreground">No adapters attempted.</span>
        )}
      </div>
    </Card>
  );
}

function KeyValueCard({
  title,
  icon,
  payload,
  language,
}: {
  title: string;
  icon: Parameters<typeof Icon>[0]["name"];
  payload: Record<string, unknown> | undefined;
  language: string;
}) {
  const code = payload ? JSON.stringify(payload, null, 2) : "// none";
  return (
    <Card className="gap-2 p-4">
      <div className="flex items-center gap-2">
        <Icon name={icon} size={14} aria-hidden />
        <h4 className="text-sm font-medium">{title}</h4>
      </div>
      <CodeBlock code={code} language={language} />
    </Card>
  );
}

export function ExecutionDetail() {
  const executionId = useStudio((s) => s.selectedExecutionId);
  const openAction = useStudio((s) => s.openAction);
  const openExecution = useStudio((s) => s.openExecution);
  const { data, loading, error } = useApi<Execution>(
    () => (executionId ? api.getExecution(executionId) : Promise.reject(new Error("no-id"))),
    [executionId],
    { enabled: !!executionId },
  );
  const [rerunning, setRerunning] = React.useState(false);
  const [replay, setReplay] = React.useState<Execution | null>(null);
  const [replaying, setReplaying] = React.useState(false);

  const rerun = async () => {
    if (!data) return;
    setRerunning(true);
    try {
      const result = await api.runAction(data.actionId, data.inputs, "manual");
      toast.success("Re-ran", { description: `New execution ${result.id.slice(0, 12)}…` });
      openExecution(result.id);
    } catch {
      toast.error("Re-run failed", { description: "Backend unreachable." });
    } finally {
      setRerunning(false);
    }
  };

  const replayCompare = async () => {
    if (!data) return;
    setReplaying(true);
    setReplay(null);
    try {
      const result = await api.runAction(data.actionId, data.inputs, "manual");
      setReplay(result);
      toast.success("Replay complete", {
        description: `Status: ${result.status} · ${result.durationMs}ms`,
      });
    } catch {
      toast.error("Replay failed", { description: "Backend unreachable." });
    } finally {
      setReplaying(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <EmptyState
        icon="alert"
        title="Could not load execution"
        description="Backend may be unreachable or the execution id is invalid."
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-3 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <button
              type="button"
              onClick={() => openAction(data.actionId)}
              className="inline-flex items-center gap-1.5 text-lg font-medium hover:text-accent"
            >
              <Icon name="link" size={14} aria-hidden />
              <code className="font-mono">{data.actionName}</code>
            </button>
            <div className="mt-1 flex flex-wrap items-center gap-3 er-caption text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Icon name="person" size={11} aria-hidden /> {data.caller}
              </span>
              <span className="inline-flex items-center gap-1">
                <Icon name="clock" size={11} aria-hidden /> {formatTime(data.startedAt)}
              </span>
              <span className="tabular-nums">{data.durationMs}ms</span>
              <AdapterChip adapter={data.adapter} />
              {data.riskApproved && (
                <Badge className="bg-accent text-accent-foreground">
                  <Icon name="shieldCheck" size={10} aria-hidden /> risk approved
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusDot status={data.status} />
            <Button
              size="sm"
              variant="outline"
              onClick={replayCompare}
              disabled={replaying}
            >
              <Icon name="diff" size={12} aria-hidden />
              {replaying ? "Replaying…" : "Replay & compare"}
            </Button>
            <Button size="sm" variant="outline" onClick={rerun} disabled={rerunning}>
              <Icon name="sync" size={12} aria-hidden />
              {rerunning ? "Re-running…" : "Re-run"}
            </Button>
          </div>
        </div>
      </Card>

      {replay && (
        <ReplayCompareCard original={data} replay={replay} onClose={() => setReplay(null)} />
      )}

      {data.errorMessage && (
        <Card className="gap-2 border-destructive/40 bg-destructive/10 p-4">
          <div className="flex items-center gap-2">
            <Icon name="alertFill" size={14} className="text-destructive" aria-hidden />
            <h4 className="text-sm font-medium text-destructive">Error</h4>
          </div>
          <p className="font-mono text-xs text-foreground">{data.errorMessage}</p>
        </Card>
      )}

      <FallbackChain execution={data} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <KeyValueCard title="Inputs" icon="arrowDown" payload={data.inputs} language="json" />
        <KeyValueCard
          title="Outputs"
          icon="arrowRight"
          payload={data.outputs}
          language="json"
        />
      </div>

      <Card className="gap-2 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="graph" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Trace</h4>
            <span className="er-caption text-muted-foreground">
              {data.traces.length} events
            </span>
          </div>
        </div>
        <TraceTimeline traces={data.traces} />
      </Card>

      <Card className="gap-2 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="tasklist" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Postconditions</h4>
          </div>
          {data.postconditionsMet === undefined ? (
            <span className="er-caption text-muted-foreground">not evaluated</span>
          ) : data.postconditionsMet ? (
            <Badge className="bg-accent text-accent-foreground">
              <Icon name="check" size={10} aria-hidden /> met
            </Badge>
          ) : (
            <Badge variant="destructive">
              <Icon name="x" size={10} aria-hidden /> not met
            </Badge>
          )}
        </div>
        {data.postconditionsMet === false && (
          <p className="er-caption text-muted-foreground">
            One or more assertions failed — the engine will propose a repair.
          </p>
        )}
      </Card>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* ReplayCompareCard — side-by-side trace diff after replay           */
/* ------------------------------------------------------------------ */

function ReplayCompareCard({
  original,
  replay,
  onClose,
}: {
  original: Execution;
  replay: Execution;
  onClose: () => void;
}) {
  const statusChanged = original.status !== replay.status;
  const durationDelta = replay.durationMs - original.durationMs;
  const adapterChanged = original.adapter !== replay.adapter;
  const tracesChanged = original.traces.length !== replay.traces.length;

  return (
    <Card className="er-card-raised gap-3 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="grid size-8 place-items-center rounded-md"
            style={{
              background:
                "linear-gradient(135deg, rgba(107,88,118,0.40), rgba(122,133,72,0.18))",
              color: "#E8E0D4",
            }}
          >
            <Icon name="diff" size={16} aria-hidden />
          </span>
          <div>
            <h4 className="text-sm font-medium">Replay comparison</h4>
            <p className="er-caption text-muted-foreground">
              Same inputs, run just now — spot drift at a glance.
            </p>
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Dismiss comparison">
          <Icon name="x" size={14} aria-hidden />
        </Button>
      </div>

      {/* Delta summary chips */}
      <div className="flex flex-wrap gap-2">
        {statusChanged ? (
          <Badge className="er-pill-warn">
            <Icon name="alert" size={10} aria-hidden /> status: {original.status} → {replay.status}
          </Badge>
        ) : (
          <Badge className="er-pill-success">
            <Icon name="check" size={10} aria-hidden /> status unchanged
          </Badge>
        )}
        {adapterChanged && (
          <Badge className="er-pill-warn">
            <Icon name="arrowRight" size={10} aria-hidden /> adapter: {original.adapter} → {replay.adapter}
          </Badge>
        )}
        <Badge
          className={
            Math.abs(durationDelta) > 200 ? "er-pill-warn" : "er-pill-neutral"
          }
        >
          <Icon name="clock" size={10} aria-hidden /> duration {durationDelta >= 0 ? "+" : ""}
          {durationDelta}ms
        </Badge>
        {tracesChanged && (
          <Badge className="er-pill-warn">
            <Icon name="graph" size={10} aria-hidden /> traces: {original.traces.length} → {replay.traces.length}
          </Badge>
        )}
      </div>

      {/* Side-by-side traces */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="er-caption text-muted-foreground mb-2 flex items-center gap-1.5">
            <Icon name="history" size={12} aria-hidden /> Original ·{" "}
            {new Date(original.startedAt).toLocaleTimeString()}
          </p>
          <TraceTimeline traces={original.traces} />
        </div>
        <div>
          <p className="er-caption text-muted-foreground mb-2 flex items-center gap-1.5">
            <Icon name="sync" size={12} aria-hidden /> Replay · now
          </p>
          <TraceTimeline traces={replay.traces} />
        </div>
      </div>

      {/* Outputs diff */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <KeyValueCard
          title="Original outputs"
          icon="arrowRight"
          payload={original.outputs}
          language="json"
        />
        <KeyValueCard
          title="Replay outputs"
          icon="arrowRight"
          payload={replay.outputs}
          language="json"
        />
      </div>
    </Card>
  );
}
