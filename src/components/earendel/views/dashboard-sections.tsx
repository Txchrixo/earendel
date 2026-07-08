"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Icon, type ErIconName } from "../icon";
import { useApi } from "../use-api";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import { toast } from "@/hooks/use-toast";
import type {
  DashboardStats,
  MonitoringSummary,
  TimeSeries,
  Execution,
  RepairProposal,
} from "@/lib/earendel/types";
import {
  StatCard,
  SectionTitle,
  EmptyState,
  StatusDot,
  AdapterChip,
} from "../primitives";

/* ------------------------------------------------------------------ */
/* Hero                                                               */
/* ------------------------------------------------------------------ */

export function Hero() {
  const setView = useStudio((s) => s.setView);
  return (
    <Card className="er-surface relative overflow-hidden rounded-xl border-border p-8">
      <div className="relative z-10 max-w-3xl">
        <p className="er-caption mb-3 flex items-center gap-1.5 text-accent">
          <Icon name="telescope" size={12} aria-hidden /> Earendel Studio
        </p>
        <h1 className="er-hero font-heading">
          Turn repeated human workflows into typed, monitored, repairable agent tools.
        </h1>
        <p className="er-body mt-4 max-w-2xl text-muted-foreground">
          Record an authorised workflow once. Earendel compiles it to a typed action with
          inputs, outputs, permissions and tests — backed by a multi-adapter execution
          engine that validates, repairs and publishes as MCP / REST / SDK.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button size="lg" onClick={() => setView("recorder")}>
            <Icon name="recorder" size={16} aria-hidden /> Record a workflow
          </Button>
          <Button size="lg" variant="outline" onClick={() => setView("actions")}>
            <Icon name="actions" size={16} aria-hidden /> Browse actions
          </Button>
        </div>
      </div>
      <Icon
        name="telescope"
        size={420}
        className="pointer-events-none absolute -right-16 -top-8 text-primary/10"
        aria-hidden
      />
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Stats                                                              */
/* ------------------------------------------------------------------ */

export function StatsSection() {
  const { data, loading, error } = useApi<DashboardStats>(() => api.stats(), []);
  if (error) {
    return (
      <EmptyState
        icon="meter"
        title="Backend connecting…"
        description="Live stats will appear once the FastAPI service is reachable."
      />
    );
  }
  const s = data;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard icon="connectors" label="Connectors" value={s?.connectors ?? 0} loading={loading} />
      <StatCard
        icon="actions"
        label="Published actions"
        value={s?.publishedActions ?? 0}
        loading={loading}
      />
      <StatCard
        icon="executions"
        label="Executions today"
        value={s?.executionsToday ?? 0}
        loading={loading}
      />
      <StatCard
        icon="checkCircle"
        label="Success rate (24h)"
        value={s ? `${Math.round(s.successRate * 100)}%` : "—"}
        delta={s ? `${s.openRepairs} open repairs` : undefined}
        trend={s && s.successRate >= 0.9 ? "up" : "flat"}
        loading={loading}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Pipeline                                                           */
/* ------------------------------------------------------------------ */

const PIPELINE: { icon: ErIconName; title: string; desc: string }[] = [
  { icon: "recorder", title: "Record", desc: "Capture an authorised human workflow." },
  { icon: "code", title: "Compile", desc: "Generate a typed action contract." },
  { icon: "shieldCheck", title: "Validate & repair", desc: "Canaries + auto-healed selectors." },
  { icon: "publishing", title: "Publish", desc: "MCP / REST / SDK / webhook." },
];

export function PipelineSection() {
  return (
    <section>
      <SectionTitle
        icon="workflow"
        title="The Earendel pipeline"
        subtitle="From a captured workflow to a callable agent tool"
      />
      <div className="flex flex-col gap-2 md:flex-row md:items-stretch">
        {PIPELINE.map((step, i) => (
          <React.Fragment key={step.title}>
            <Card className="er-card-raised er-lift flex-1 gap-2 p-4">
              <div className="flex items-center gap-2">
                <span
                  className="grid size-7 place-items-center rounded-md font-mono text-xs font-bold"
                  style={{
                    background: `linear-gradient(135deg, rgba(107,88,118,${0.3 + i * 0.12}), rgba(122,133,72,${0.12 + i * 0.08}))`,
                    color: "#E8E0D4",
                    boxShadow: "inset 0 0 0 1px rgba(232,224,212,0.08)",
                  }}
                >
                  {i + 1}
                </span>
                <Icon name={step.icon} size={14} className="text-accent" aria-hidden />
              </div>
              <p className="font-heading text-lg leading-tight mt-1">{step.title}</p>
              <p className="er-caption text-muted-foreground">{step.desc}</p>
            </Card>
            {i < PIPELINE.length - 1 && (
              <div className="flex items-center justify-center px-1 py-1 md:py-0">
                <Icon
                  name="arrowRight"
                  size={18}
                  className="text-muted-foreground"
                  aria-hidden
                />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Reliability at a glance                                            */
/* ------------------------------------------------------------------ */

function Bar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 er-caption text-muted-foreground">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-sm tabular-nums">{value}</span>
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: React.ReactNode; icon: ErIconName }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="er-caption flex items-center gap-1 text-muted-foreground">
        <Icon name={icon} size={12} aria-hidden /> {label}
      </span>
      <span className="font-heading text-2xl leading-none tabular-nums">{value}</span>
    </div>
  );
}

/** Small inline SVG sparkline from real time-series points. */
function HealthSpark({ points }: { points: number[] }) {
  if (points.length === 0) return null;
  const w = 120;
  const h = 36;
  const max = 1;
  const min = 0.6;
  const stepX = w / Math.max(1, points.length - 1);
  const coords = points.map((p, i) => {
    const x = i * stepX;
    const y = h - ((p - min) / (max - min)) * h;
    return [x, y];
  });
  const path = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${path} L${w},${h} L0,${h} Z`;
  const lastX = coords[coords.length - 1][0];
  const lastY = coords[coords.length - 1][1];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="overflow-visible">
      <defs>
        <linearGradient id="er-spark" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7A8548" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#7A8548" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#er-spark)" />
      <path d={path} fill="none" stroke="#7A8548" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="2.5" fill="#7A8548" />
      <circle cx={lastX} cy={lastY} r="5" fill="#7A8548" fillOpacity="0.2" />
    </svg>
  );
}

export function ReliabilitySection() {
  const { data, loading, error } = useApi<MonitoringSummary>(() => api.monitoring(), []);
  const { data: ts } = useApi<TimeSeries>(() => api.timeseries(24), []);
  const successPct = data ? Math.round(data.successRate24h * 100) : 0;
  // Sample the 24h series down to ~12 points for the sparkline, else fall back.
  const sparkPoints = (ts?.points ?? []).map((p) => p.successRate);
  const sampled = sparkPoints.length > 12
    ? sparkPoints.filter((_, i) => i % Math.ceil(sparkPoints.length / 12) === 0).slice(-12)
    : sparkPoints;
  return (
    <section>
      <SectionTitle
        icon="pulse"
        title="Reliability at a glance"
        subtitle="Live canary coverage and repair queue"
      />
      <Card className="er-card-raised gap-4 p-5">
        {error ? (
          <p className="er-caption text-muted-foreground">
            Backend connecting… monitoring data will appear here shortly.
          </p>
        ) : loading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1 space-y-2.5">
                <Bar label="Healthy" value={data?.healthy ?? 0} total={data?.totalActions ?? 1} color="bg-accent" />
                <Bar label="Degraded" value={data?.degraded ?? 0} total={data?.totalActions ?? 1} color="bg-chart-4" />
                <Bar label="Broken" value={data?.broken ?? 0} total={data?.totalActions ?? 1} color="bg-destructive" />
              </div>
              <div className="flex flex-col items-end gap-1 border-l border-border pl-4">
                <span className="er-caption text-muted-foreground flex items-center gap-1">
                  <Icon name="graph" size={12} aria-hidden /> Success 24h
                </span>
                <span className="font-heading text-3xl leading-none tabular-nums er-gradient-text">
                  {successPct}%
                </span>
                <HealthSpark points={sampled.length > 0 ? sampled : [0.82, 0.79, 0.85, 0.88, 0.84, 0.91, data?.successRate24h ?? 0.85]} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-4">
              <Metric label="Canary pass" value={data ? `${Math.round(data.canaryPassRate * 100)}%` : "—"} icon="checkCircle" />
              <Metric label="Open repairs" value={data?.openRepairs ?? 0} icon="tools" />
              <Metric label="Executions 24h" value={data?.executions24h ?? 0} icon="executions" />
              <Metric label="MTTR" value={data ? `${data.mttrHours.toFixed(1)}h` : "—"} icon="clock" />
            </div>
          </>
        )}
      </Card>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Recent executions                                                  */
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

export function RecentExecutionsSection() {
  const { data, loading, error } = useApi<Execution[]>(() => api.listExecutions(), []);
  const openExecution = useStudio((s) => s.openExecution);
  const setView = useStudio((s) => s.setView);
  const items = (data ?? []).slice(0, 6);

  return (
    <section>
      <SectionTitle
        icon="history"
        title="Recent executions"
        subtitle="Latest runs across all actions"
        action={
          <Button variant="ghost" size="sm" onClick={() => setView("executions")}>
            View all <Icon name="arrowRight" size={14} aria-hidden />
          </Button>
        }
      />
      <Card className="gap-0 p-0">
        {error ? (
          <div className="p-4">
            <p className="er-caption text-muted-foreground">Backend connecting… no executions yet.</p>
          </div>
        ) : loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState icon="executions" title="No executions yet" description="Run a published action from the Playground." />
        ) : (
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
                      <span className="truncate text-sm font-medium">{e.actionName}</span>
                      <AdapterChip adapter={e.adapter} />
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <StatusDot status={e.status} />
                      <span className="er-caption text-muted-foreground">
                        {e.caller} · {e.durationMs}ms · {timeAgo(e.startedAt)}
                      </span>
                    </div>
                  </div>
                  <Icon name="chevronRight" size={16} className="text-muted-foreground" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Open repair proposals                                              */
/* ------------------------------------------------------------------ */

export function OpenRepairsSection() {
  const { data, loading, error, refetch } = useApi<RepairProposal[]>(
    () => api.listRepairs(),
    [],
  );
  const [resolvingId, setResolvingId] = React.useState<string | null>(null);
  const pending = (data ?? []).filter((r) => r.status === "pending").slice(0, 4);

  const approve = async (id: string) => {
    setResolvingId(id);
    try {
      await api.resolveRepair(id, "approved");
      toast({ title: "Repair approved", description: "Selector updated and canary re-queued." });
      refetch();
    } catch {
      toast({ title: "Could not approve repair", description: "Backend unreachable.", variant: "destructive" });
    } finally {
      setResolvingId(null);
    }
  };

  return (
    <section>
      <SectionTitle
        icon="tools"
        title="Open repair proposals"
        subtitle="Selector drift detected by canaries"
        action={
          <Button variant="ghost" size="sm" onClick={() => useStudio.getState().setView("monitoring")}>
            Open monitoring <Icon name="arrowRight" size={14} aria-hidden />
          </Button>
        }
      />
      {error ? (
        <EmptyState icon="tools" title="No repair data yet" description="Backend connecting…" />
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : pending.length === 0 ? (
        <EmptyState icon="shieldCheck" title="No open repairs" description="All selectors are healthy." />
      ) : (
        <div className="grid gap-3">
          {pending.map((r) => (
            <motion.div
              key={r.id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Icon name="bug" size={14} className="text-chart-4" aria-hidden />
                    <span className="text-sm font-medium">
                      {r.actionId} <span className="text-muted-foreground">· v{r.actionVersion}</span>
                    </span>
                  </div>
                  <p className="er-caption mt-1 text-muted-foreground">{r.reason}</p>
                  <p className="er-caption mt-1 font-mono text-muted-foreground">
                    {r.failedSelector} → {r.candidateSelector}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <div className="text-right">
                    <p className="font-heading text-lg leading-none">
                      {Math.round(r.confidence * 100)}%
                    </p>
                    <p className="er-caption text-muted-foreground">confidence</p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => approve(r.id)}
                    disabled={resolvingId === r.id}
                  >
                    <Icon name="check" size={14} aria-hidden />
                    {resolvingId === r.id ? "Approving…" : "Approve"}
                  </Button>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* SystemHealthStrip — /healthz + /readyz status indicators           */
/* ------------------------------------------------------------------ */

interface HealthStatus {
  status: string;
  checks?: Record<string, string>;
  counts?: Record<string, number>;
}

function HealthPill({
  label,
  ok,
  detail,
}: {
  label: string;
  ok: boolean;
  detail?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "size-2 rounded-full",
          ok ? "bg-accent er-pulse" : "bg-destructive",
        )}
        style={{ boxShadow: "0 0 6px 0 currentColor" }}
        aria-hidden
      />
      <span className="er-caption text-muted-foreground">{label}</span>
      <span className={cn("er-caption font-mono", ok ? "text-accent" : "text-destructive")}>
        {ok ? "ok" : "down"}
      </span>
      {detail && (
        <span className="er-caption text-muted-foreground/70">· {detail}</span>
      )}
    </div>
  );
}

export function SystemHealthStrip() {
  const { data: liveness } = useApi<{ status: string }>(
    () => api.raw("/api/v1/healthz"),
    [],
    { refetchInterval: 30000 },
  );
  const { data: readiness } = useApi<HealthStatus>(
    () => api.raw("/api/v1/readyz"),
    [],
    { refetchInterval: 30000 },
  );
  const liveOk = liveness?.status === "alive";
  const readyOk = readiness?.status === "ready";
  const dbOk = readiness?.checks?.database === "ok";
  const regOk = readiness?.checks?.action_registry === "ok";

  return (
    <Card className="er-card-raised flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
      <div className="flex items-center gap-2">
        <Icon name="server" size={14} className="text-accent" aria-hidden />
        <span className="er-caption font-medium text-foreground uppercase tracking-wide">
          System health
        </span>
      </div>
      <HealthPill label="liveness" ok={liveOk} />
      <HealthPill label="readiness" ok={readyOk} />
      <HealthPill label="database" ok={dbOk} />
      <HealthPill
        label="registry"
        ok={regOk}
        detail={readiness?.counts ? `${readiness.counts.actions} actions` : undefined}
      />
      <span className="ml-auto er-caption text-muted-foreground/60">
        refreshed every 30s
      </span>
    </Card>
  );
}
