"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip as RTooltip,
  CartesianGrid,
} from "recharts";
import { toast } from "sonner";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import type {
  RepairKnowledgeEntry,
  RepairKBStats,
} from "@/lib/earendel/types";
import {
  StatCard,
  SectionTitle,
  EmptyState,
} from "../primitives";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const sourceStyle: Record<
  string,
  { label: string; pill: string; icon: "shieldCheck" | "sparkles" | "tools" }
> = {
  knowledge_base: {
    label: "KB",
    pill: "er-pill-success",
    icon: "shieldCheck",
  },
  llm: {
    label: "LLM",
    pill: "er-pill-primary",
    icon: "sparkles",
  },
  fallback: {
    label: "fallback",
    pill: "er-pill-neutral",
    icon: "tools",
  },
  manual: {
    label: "manual",
    pill: "er-pill-warn",
    icon: "tools",
  },
};

const _defaultSourceStyle = {
  label: "other",
  pill: "er-pill-neutral",
  icon: "tools" as const,
};

/* ------------------------------------------------------------------ */
/* Stat row                                                            */
/* ------------------------------------------------------------------ */

function StatRow() {
  const { data, loading, error } = useApi<RepairKBStats>(
    () => api.repairKBStats(),
    [],
    { refetchInterval: 30000 },
  );
  if (error) {
    return (
      <EmptyState
        icon="database"
        title="Backend connecting…"
        description="Repair KB stats will appear once the FastAPI service is reachable."
      />
    );
  }
  const s = data;
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard icon="database" label="Entries" value={s?.totalEntries ?? 0} loading={loading} />
      <StatCard icon="checkCircle" label="Successes" value={s?.totalSuccesses ?? 0} loading={loading} />
      <StatCard icon="sparkles" label="Auto-applied" value={s?.totalAutoApplied ?? 0} loading={loading} />
      <StatCard
        icon="meter"
        label="Avg confidence"
        value={s ? `${Math.round(s.avgConfidence * 100)}%` : "—"}
        loading={loading}
        trend={s && s.avgConfidence >= 0.85 ? "up" : "flat"}
      />
      <StatCard icon="shieldCheck" label="Active" value={s?.activeEntries ?? 0} loading={loading} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* MTTR trend chart                                                    */
/* ------------------------------------------------------------------ */

function MttrTrend({ stats }: { stats: RepairKBStats | undefined }) {
  const points = (stats?.mttrTrend ?? []).map((p) => ({
    bucket: p.bucket,
    mttr: p.mttrMs == null ? null : p.mttrMs,
  }));
  const hasData = points.some((p) => p.mttr !== null);

  return (
    <Card className="gap-2 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon name="graph" size={14} aria-hidden />
          <h3 className="er-h3">Mean time to repair</h3>
        </div>
        <span className="er-caption text-muted-foreground">
          last 7 days · per-day average
        </span>
      </div>
      {hasData ? (
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="er-mttr" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#7A8548" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#7A8548" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="bucket"
                stroke="var(--muted-foreground)"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="var(--muted-foreground)"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${v}ms`}
              />
              <RTooltip
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                formatter={(v: number) => [v == null ? "no data" : `${v}ms`, "MTTR"]}
              />
              <Area
                type="monotone"
                dataKey="mttr"
                stroke="#7A8548"
                strokeWidth={2}
                fill="url(#er-mttr)"
                connectNulls
                dot={{ r: 2.5, fill: "#7A8548" }}
                activeDot={{ r: 4 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="flex h-40 items-center justify-center text-center">
          <p className="er-caption text-muted-foreground max-w-xs">
            No repair outcomes yet. The flywheel starts spinning the first time
            a rupture is repaired — each subsequent repair on the same portal
            pattern becomes instant.
          </p>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Top domains card                                                    */
/* ------------------------------------------------------------------ */

function TopDomains({ stats }: { stats: RepairKBStats | undefined }) {
  const domains = stats?.topDomains ?? [];
  const max = domains.reduce((m, d) => Math.max(m, d.successCount), 0) || 1;

  return (
    <Card className="gap-2 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon name="globe" size={14} className="text-accent" aria-hidden />
          <h3 className="er-h3">Top domains</h3>
        </div>
        <span className="er-caption text-muted-foreground">by success count</span>
      </div>
      {domains.length === 0 ? (
        <p className="er-caption text-muted-foreground py-6 text-center">
          No domain statistics yet.
        </p>
      ) : (
        <ul className="space-y-2 py-1">
          {domains.map((d) => (
            <li key={d.domain} className="flex items-center gap-3">
              <span className="font-mono text-xs text-foreground w-32 truncate" title={d.domain}>
                {d.domain}
              </span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: `${(d.successCount / max) * 100}%` }}
                />
              </div>
              <span className="er-caption tabular-nums text-muted-foreground w-10 text-right">
                {d.successCount}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Deprecate confirmation                                              */
/* ------------------------------------------------------------------ */

function DeprecateDialog({
  entry,
  open,
  onOpenChange,
  onDeprecated,
}: {
  entry: RepairKnowledgeEntry | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onDeprecated: () => void;
}) {
  const [submitting, setSubmitting] = React.useState(false);

  if (!entry) return null;

  const handle = async () => {
    setSubmitting(true);
    try {
      await api.deprecateRepairKB(entry.id);
      toast.success("KB entry deprecated", {
        description: "The pattern is preserved for analytics but excluded from future lookups.",
      });
      onOpenChange(false);
      onDeprecated();
    } catch {
      toast.error("Could not deprecate entry", { description: "Backend unreachable." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md border-border bg-card">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 font-heading text-lg">
            <Icon name="alert" size={16} className="text-chart-4" aria-hidden />
            Deprecate KB entry?
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-1.5">
              <p>
                Deprecated entries are excluded from future KB lookups (the
                query_kb tier of the repair ladder) but preserved for analytics.
                This is the right call when a repair selector has stopped
                working on the portal.
              </p>
              <p className="font-mono text-xs text-foreground break-all">
                {entry.targetDomain} · {entry.widgetType} · {entry.intention}
              </p>
              <p className="font-mono text-xs text-muted-foreground break-all">
                was: {entry.failedSelector}
                <br />
                now: {entry.repairedSelector}
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handle}
            disabled={submitting}
            className="bg-chart-4 text-background hover:bg-chart-4/90"
          >
            <Icon name="trash" size={14} aria-hidden />
            {submitting ? "Deprecating…" : "Deprecate"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/* ------------------------------------------------------------------ */
/* KB entries table                                                    */
/* ------------------------------------------------------------------ */

function KbTable() {
  const [domain, setDomain] = React.useState<string>("");
  const { data, loading, error, refetch } = useApi<RepairKnowledgeEntry[]>(
    () => api.listRepairKB(domain || undefined),
    [domain],
  );
  const [deprecateTarget, setDeprecateTarget] = React.useState<RepairKnowledgeEntry | null>(null);

  // Build the filter dropdown from the loaded entries' domains.
  const knownDomains = React.useMemo(() => {
    const set = new Set<string>();
    for (const e of data ?? []) set.add(e.targetDomain);
    return Array.from(set).sort();
  }, [data]);

  const list = data ?? [];

  return (
    <Card className="gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon name="database" size={14} className="text-accent" aria-hidden />
          <h3 className="er-h3">Knowledge entries</h3>
          <Badge variant="outline" className="er-caption">
            {list.length}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Select value={domain || "all"} onValueChange={(v) => setDomain(v === "all" ? "" : v)}>
            <SelectTrigger size="sm" className="w-48" aria-label="Filter by domain">
              <SelectValue placeholder="all domains" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">all domains</SelectItem>
              {knownDomains.map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" variant="outline" className="rounded-full" onClick={refetch}>
            <Icon name="sync" size={12} aria-hidden /> Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <EmptyState
          icon="database"
          title="Backend connecting…"
          description="Repair KB entries will appear here once the FastAPI service is reachable."
        />
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          icon="database"
          title="No repairs learned yet"
          description="When an execution fails and is repaired, the pattern is stored here for cross-client reuse."
        />
      ) : (
        <div className="max-h-96 overflow-y-auto er-scroll rounded-md border border-border">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead className="w-32">Domain</TableHead>
                <TableHead className="w-20">Widget</TableHead>
                <TableHead className="w-24">Intention</TableHead>
                <TableHead>Failed selector</TableHead>
                <TableHead>Repaired selector</TableHead>
                <TableHead className="w-28">Confidence</TableHead>
                <TableHead className="w-20">Success</TableHead>
                <TableHead className="w-20">Auto-applied</TableHead>
                <TableHead className="w-20">Source</TableHead>
                <TableHead className="w-20">Status</TableHead>
                <TableHead className="w-24">Last used</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.map((e) => {
                const src = sourceStyle[e.source] ?? _defaultSourceStyle;
                const sr =
                  e.successRate ??
                  (e.successCount + e.failureCount > 0
                    ? e.successCount / (e.successCount + e.failureCount)
                    : null);
                return (
                  <TableRow key={e.id} className="hover:bg-secondary/40">
                    <TableCell>
                      <span className="font-mono text-xs text-foreground truncate block" title={e.targetDomain}>
                        {e.targetDomain}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="er-pill-neutral">
                        {e.widgetType}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="er-caption text-muted-foreground">{e.intention}</span>
                    </TableCell>
                    <TableCell className="max-w-[20ch]">
                      <code className="font-mono text-xs text-muted-foreground break-all line-clamp-2">
                        {e.failedSelector}
                      </code>
                    </TableCell>
                    <TableCell className="max-w-[20ch]">
                      <code className="font-mono text-xs text-foreground break-all line-clamp-2">
                        {e.repairedSelector}
                      </code>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={e.confidence * 100} className="h-1.5 bg-secondary" />
                        <span className="er-caption tabular-nums text-muted-foreground w-8 text-right">
                          {Math.round(e.confidence * 100)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {sr === null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <span className={cn(sr >= 0.9 ? "text-accent" : "text-chart-4")}>
                          {Math.round(sr * 100)}%
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="tabular-nums text-muted-foreground">
                      {e.autoAppliedCount}
                    </TableCell>
                    <TableCell>
                      <Badge className={cn("border-transparent", src.pill)}>
                        <Icon name={src.icon} size={10} aria-hidden /> {src.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={cn(
                          "border-transparent",
                          e.status === "active" ? "er-pill-success" : "er-pill-danger",
                        )}
                      >
                        {e.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="er-caption text-muted-foreground">
                      {timeAgo(e.lastUsedAt)}
                    </TableCell>
                    <TableCell>
                      {e.status === "active" && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-full"
                          onClick={() => setDeprecateTarget(e)}
                        >
                          <Icon name="trash" size={11} aria-hidden /> Deprecate
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <DeprecateDialog
        entry={deprecateTarget}
        open={deprecateTarget !== null}
        onOpenChange={(o) => { if (!o) setDeprecateTarget(null); }}
        onDeprecated={refetch}
      />
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* RepairKBView                                                        */
/* ------------------------------------------------------------------ */

export function RepairKBView() {
  const { data: stats } = useApi<RepairKBStats>(() => api.repairKBStats(), []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="database"
        title="Repair Knowledge Base"
        subtitle="Cross-client repair flywheel. Every rupture repaired makes the next one instant for everyone."
      />
      <StatRow />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <MttrTrend stats={stats} />
        <TopDomains stats={stats} />
      </div>
      <KbTable />
    </motion.div>
  );
}

export default RepairKBView;
