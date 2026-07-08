"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { toast } from "sonner";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import type {
  MonitoringSummary,
  TimeSeries,
  TypedAction,
  RepairProposal,
} from "@/lib/earendel/types";
import {
  StatCard,
  SectionTitle,
  EmptyState,
  StatusDot,
  CodeBlock,
} from "../primitives";
import { RepairApprovalDialog } from "./monitoring-sections";

/* ------------------------------------------------------------------ */
/* Stat row                                                           */
/* ------------------------------------------------------------------ */

function StatRow() {
  const { data, loading, error } = useApi<MonitoringSummary>(
    () => api.monitoring(),
    [],
    { refetchInterval: 15000 },
  );
  if (error) {
    return (
      <EmptyState
        icon="monitoring"
        title="Backend connecting…"
        description="Live monitoring data will appear once the FastAPI service is reachable."
      />
    );
  }
  const s = data;
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-4">
      <StatCard icon="checkCircle" label="Healthy" value={s?.healthy ?? 0} loading={loading} />
      <StatCard
        icon="alert"
        label="Degraded"
        value={s?.degraded ?? 0}
        loading={loading}
        trend={s && s.degraded > 0 ? "down" : "up"}
        delta={s && s.degraded > 0 ? "needs attention" : "all clear"}
      />
      <StatCard
        icon="xCircle"
        label="Broken"
        value={s?.broken ?? 0}
        loading={loading}
        trend={s && s.broken > 0 ? "down" : "flat"}
      />
      <StatCard
        icon="beaker"
        label="Canary pass"
        value={s ? `${Math.round(s.canaryPassRate * 100)}%` : "—"}
        loading={loading}
      />
      <StatCard icon="tools" label="Open repairs" value={s?.openRepairs ?? 0} loading={loading} />
      <StatCard
        icon="executions"
        label="Executions 24h"
        value={s?.executions24h ?? 0}
        loading={loading}
      />
      <StatCard
        icon="meter"
        label="Success 24h"
        value={s ? `${Math.round(s.successRate24h * 100)}%` : "—"}
        loading={loading}
        trend={s && s.successRate24h >= 0.9 ? "up" : "down"}
      />
      <StatCard
        icon="clock"
        label="MTTR"
        value={s ? `${s.mttrHours.toFixed(1)}h` : "—"}
        loading={loading}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Canary board                                                       */
/* ------------------------------------------------------------------ */

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function CanaryBoard() {
  const { data, loading, error, refetch } = useApi<TypedAction[]>(
    () => api.listActions(),
    [],
  );
  const [running, setRunning] = React.useState(false);

  const runAll = async () => {
    if (!data || data.length === 0) return;
    setRunning(true);
    let ok = 0;
    for (const a of data) {
      try {
        await api.runCanary(a.id);
        ok += 1;
      } catch {
        /* keep going */
      }
    }
    setRunning(false);
    if (ok > 0) {
      toast.success("Canaries queued", {
        description: `${ok} synthetic run${ok === 1 ? "" : "s"} dispatched.`,
      });
      refetch();
    } else {
      toast.error("Could not queue canaries", { description: "Backend unreachable." });
    }
  };

  const rows = (data ?? []).flatMap((a) =>
    a.canary.map((c) => ({ action: a, canary: c })),
  );

  return (
    <Card className="gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon name="beaker" size={14} className="text-accent" aria-hidden />
          <h3 className="er-h3">Canary board</h3>
        </div>
        <Button size="sm" variant="outline" onClick={runAll} disabled={running || !data}>
          <Icon name="sync" size={12} aria-hidden />
          {running ? "Queuing…" : "Run all canaries"}
        </Button>
      </div>
      {error ? (
        <p className="er-caption text-muted-foreground">Backend connecting…</p>
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon="beaker"
          title="No canaries scheduled"
          description="Canaries validate published actions continuously."
        />
      ) : (
        <ul className="divide-y divide-border">
          {rows.map(({ action, canary }) => (
            <li key={canary.id} className="grid gap-2 py-3 sm:grid-cols-[1.5fr_1fr_1fr]">
              <div>
                <div className="flex items-center gap-2">
                  <code className="font-mono text-sm">{action.name}</code>
                  <Badge variant="outline" className="er-caption">
                    v{action.version}
                  </Badge>
                </div>
                <p className="er-caption mt-0.5 text-muted-foreground">
                  <Icon name="calendar" size={11} className="mr-1 inline" aria-hidden />
                  {canary.schedule} · last run {timeAgo(canary.lastRun)}
                </p>
              </div>
              <div>
                <StatusDot
                  status={
                    canary.lastStatus === "passed"
                      ? "success"
                      : canary.lastStatus === "warning"
                        ? "human_review"
                        : "failed"
                  }
                />
                <p className="er-caption mt-0.5 text-muted-foreground">
                  {canary.assertions.filter((a) => a.passed).length}/
                  {canary.assertions.length} assertions
                </p>
              </div>
              <div>
                <div className="flex items-center justify-between er-caption text-muted-foreground">
                  <span>pass rate</span>
                  <span>{Math.round(canary.passRate * 100)}%</span>
                </div>
                <Progress value={canary.passRate * 100} className="mt-1 bg-secondary" />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Repair proposals                                                   */
/* ------------------------------------------------------------------ */

function RepairExplainer() {
  return (
    <Collapsible>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="w-full justify-between">
          <span className="inline-flex items-center gap-2">
            <Icon name="lightbulb" size={14} className="text-chart-4" aria-hidden />
            How repair works
          </span>
          <Icon name="chevronDown" size={12} aria-hidden />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="space-y-2 px-1 pt-2 er-caption text-muted-foreground">
          <p>
            When a canary detects that a recorded selector no longer matches,
            Earendel diffs the live DOM against the snapshot, asks the LLM for a
            candidate selector, and stores a <span className="text-foreground">RepairProposal</span> with a
            confidence score.
          </p>
          <p>
            Approving a proposal patches the action's preconditions and bumps
            the patch version. Rejected proposals are kept for audit. Above
            0.90 confidence, Earendel can auto-apply the patch.
          </p>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function RepairCard({
  r,
  onResolve,
}: {
  r: RepairProposal;
  onResolve: (id: string, decision: "approved" | "rejected") => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const handle = (decision: "approved" | "rejected") => {
    setBusy(true);
    onResolve(r.id, decision);
    setTimeout(() => setBusy(false), 600);
  };
  return (
    <motion.div layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="er-card-raised gap-3 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Icon name="bug" size={14} className="text-chart-4" aria-hidden />
              <code className="font-mono text-sm">
                {r.actionId.slice(0, 16)}…
              </code>
              <Badge variant="outline" className="er-pill-neutral">
                v{r.actionVersion}
              </Badge>
              <Badge
                className={cn(
                  r.status === "pending" && "er-pill-warn",
                  (r.status === "approved" || r.status === "auto_applied") && "er-pill-success",
                  r.status === "rejected" && "er-pill-danger",
                )}
              >
                {r.status.replace("_", " ")}
              </Badge>
              {r.confidence >= 0.9 && r.status === "pending" && (
                <Badge className="er-pill-success">
                  <Icon name="sparkles" size={10} aria-hidden /> auto-apply eligible
                </Badge>
              )}
            </div>
            <p className="er-caption mt-2 text-muted-foreground">{r.reason}</p>
            <p className="er-caption mt-1 text-muted-foreground">
              <Icon name="clock" size={11} className="mr-1 inline" aria-hidden />
              detected {timeAgo(r.detectedAt)} · {r.candidateLabel}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span className="font-heading text-2xl leading-none tabular-nums">
              {Math.round(r.confidence * 100)}%
            </span>
            <span className="er-caption text-muted-foreground">confidence</span>
          </div>
        </div>
        <Progress value={r.confidence * 100} className="bg-secondary" />
        <CodeBlock
          code={`- ${r.failedSelector}\n+ ${r.candidateSelector}`}
          language="diff"
        />
        {r.status === "pending" && (
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => setDialogOpen(true)} disabled={busy}>
              <Icon name="eye" size={12} aria-hidden /> Review &amp; patch
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handle("rejected")}
              disabled={busy}
            >
              <Icon name="x" size={12} aria-hidden /> Reject
            </Button>
          </div>
        )}
        <RepairApprovalDialog
          proposal={r}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          onResolve={handle}
        />
      </Card>
    </motion.div>
  );
}

function RepairProposals() {
  const { data, loading, error, refetch } = useApi<RepairProposal[]>(
    () => api.listRepairs(),
    [],
  );
  const [filter, setFilter] = React.useState<"pending" | "resolved">("pending");
  const [resolving, setResolving] = React.useState<string | null>(null);

  const resolve = async (id: string, decision: "approved" | "rejected") => {
    setResolving(id);
    try {
      await api.resolveRepair(id, decision);
      toast.success(
        decision === "approved" ? "Repair approved" : "Repair rejected",
        {
          description:
            decision === "approved"
              ? "Selector patched and canary re-queued."
              : "Proposal dismissed for audit.",
        },
      );
      refetch();
    } catch {
      toast.error("Could not resolve repair", { description: "Backend unreachable." });
    } finally {
      setResolving(null);
    }
  };

  void resolving;

  const list = (data ?? []).filter((r) =>
    filter === "pending" ? r.status === "pending" : r.status !== "pending",
  );

  return (
    <Card className="gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon name="tools" size={14} className="text-chart-4" aria-hidden />
          <h3 className="er-h3">Repair proposals</h3>
        </div>
        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
          {(["pending", "resolved"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                "rounded px-2 py-1 er-caption capitalize",
                filter === f ? "bg-secondary text-foreground" : "text-muted-foreground",
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <RepairExplainer />
      {error ? (
        <p className="er-caption text-muted-foreground">Backend connecting…</p>
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          icon="shieldCheck"
          title={filter === "pending" ? "No open repairs" : "No resolved repairs"}
          description={
            filter === "pending"
              ? "All selectors are healthy."
              : "Approve or reject a pending repair to see it here."
          }
        />
      ) : (
        <div className="grid gap-3">
          {list.map((r) => (
            <RepairCard key={r.id} r={r} onResolve={resolve} />
          ))}
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Reliability trend (placeholder sparkline)                          */
/* ------------------------------------------------------------------ */

const TREND_DATA = [
  { t: "Mon", rate: 0.86 },
  { t: "Tue", rate: 0.91 },
  { t: "Wed", rate: 0.94 },
  { t: "Thu", rate: 0.89 },
  { t: "Fri", rate: 0.92 },
  { t: "Sat", rate: 0.96 },
  { t: "Sun", rate: 0.94 },
];

function ReliabilityTrend() {
  const { data: mon } = useApi<MonitoringSummary>(() => api.monitoring(), []);
  const { data: ts } = useApi<TimeSeries>(() => api.timeseries(24), []);
  // Use real hourly points from the timeseries endpoint; fall back to the
  // deterministic 7-day series if the endpoint is unavailable.
  const latest = mon ? mon.successRate24h : 0.94;
  const series = (ts?.points ?? []).map((p) => ({
    t: p.hourLabel,
    rate: p.successRate,
    total: p.total,
  }));
  const fallback = TREND_DATA.map((d, i) =>
    i === TREND_DATA.length - 1 ? { ...d, rate: latest } : d,
  );
  const chartData = series.length > 0 ? series : fallback;
  return (
    <Card className="er-card-raised gap-2 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon name="graph" size={14} aria-hidden />
          <h3 className="er-h3">Reliability trend</h3>
        </div>
        <span className="er-caption text-muted-foreground">
          {series.length > 0 ? "last 24 hours" : "last 7 days"}
        </span>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="t"
              stroke="var(--muted-foreground)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[0.6, 1]}
              stroke="var(--muted-foreground)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
            />
            <Tooltip
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontSize: 12,
              }}
              formatter={(v: number) => [`${Math.round(v * 100)}%`, "success"]}
            />
            <Line
              type="monotone"
              dataKey="rate"
              stroke="var(--chart-2)"
              strokeWidth={2}
              dot={{ r: 2.5, fill: "var(--chart-2)" }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* MonitoringView                                                     */
/* ------------------------------------------------------------------ */

export function MonitoringView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="monitoring"
        title="Monitoring & Repair"
        subtitle="Continuous validation catches drift before your agents do."
      />
      <StatRow />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CanaryBoard />
        <ReliabilityTrend />
      </div>
      <RepairProposals />

    </motion.div>
  );
}

export default MonitoringView;
