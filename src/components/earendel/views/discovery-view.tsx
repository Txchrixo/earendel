"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import type {
  DiscoveredEndpoint,
  DiscoveryStats,
} from "@/lib/earendel/types";
import {
  StatCard,
  SectionTitle,
  EmptyState,
  CodeBlock,
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

function methodColor(method: string): string {
  const m = method.toUpperCase();
  if (m === "GET") return "er-pill-success";
  if (m === "POST") return "er-pill-primary";
  if (m === "PUT" || m === "PATCH") return "er-pill-warn";
  if (m === "DELETE") return "er-pill-danger";
  return "er-pill-neutral";
}

function prettyJson(value: string): string {
  if (!value) return "// empty";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

/* ------------------------------------------------------------------ */
/* Stat row                                                            */
/* ------------------------------------------------------------------ */

function StatRow() {
  const { data, loading, error } = useApi<DiscoveryStats>(
    () => api.discoveryStats(),
    [],
    { refetchInterval: 30000 },
  );
  if (error) {
    return (
      <EmptyState
        icon="globe"
        title="Backend connecting…"
        description="Discovery stats will appear once the FastAPI service is reachable."
      />
    );
  }
  const s = data;
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <StatCard icon="globe" label="Endpoints" value={s?.totalEndpoints ?? 0} loading={loading} />
      <StatCard icon="checkCircle" label="Active" value={s?.activeEndpoints ?? 0} loading={loading} />
      <StatCard
        icon="alert"
        label="Stale"
        value={s?.staleEndpoints ?? 0}
        loading={loading}
        trend={s && s.staleEndpoints > 0 ? "down" : "flat"}
      />
      <StatCard
        icon="meter"
        label="Replay success"
        value={s ? `${Math.round(s.successRate * 100)}%` : "—"}
        loading={loading}
        trend={s && s.successRate >= 0.9 ? "up" : "flat"}
        delta={s ? `${s.totalReplays} replays` : undefined}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Analyze HAR dialog                                                  */
/* ------------------------------------------------------------------ */

function AnalyzeHarDialog({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onDone: () => void;
}) {
  const [harText, setHarText] = React.useState("");
  const [actionName, setActionName] = React.useState("");
  const [connectorId, setConnectorId] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  const reset = () => {
    setHarText("");
    setActionName("");
    setConnectorId("");
  };

  const handle = async () => {
    const name = actionName.trim();
    if (!name) {
      toast.error("Action name required", {
        description: "Tell the analyzer which action this HAR belongs to.",
      });
      return;
    }
    let har: unknown;
    try {
      har = JSON.parse(harText);
    } catch {
      toast.error("Invalid HAR JSON", {
        description: "Paste a valid HAR document (Chrome DevTools → Copy as HAR).",
      });
      return;
    }
    setSubmitting(true);
    try {
      const found = await api.analyzeHar(
        har,
        name,
        connectorId.trim() || undefined,
      );
      toast.success("HAR analyzed", {
        description: `${found.length} candidate endpoint${found.length === 1 ? "" : "s"} stored for replay.`,
      });
      reset();
      onOpenChange(false);
      onDone();
    } catch {
      toast.error("Analysis failed", { description: "Backend unreachable." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <DialogContent className="max-w-2xl border-border bg-card">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-heading text-xl">
            <span className="grid size-8 place-items-center rounded-md bg-secondary text-muted-foreground">
              <Icon name="upload" size={16} aria-hidden />
            </span>
            Analyze HAR capture
          </DialogTitle>
          <DialogDescription>
            Paste a HAR document captured while performing a workflow. The analyzer
            clusters requests, scores them by business signal, and stores the top
            candidates as replayable internal endpoints.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label className="er-caption text-muted-foreground" htmlFor="har-action">
                Action name
              </label>
              <Input
                id="har-action"
                value={actionName}
                onChange={(e) => setActionName(e.target.value)}
                placeholder="e.g. downloadInvoice"
                className="font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="er-caption text-muted-foreground" htmlFor="har-connector">
                Connector ID (optional)
              </label>
              <Input
                id="har-connector"
                value={connectorId}
                onChange={(e) => setConnectorId(e.target.value)}
                placeholder="conn_xxx"
                className="font-mono"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="er-caption text-muted-foreground" htmlFor="har-body">
              HAR JSON
            </label>
            <Textarea
              id="har-body"
              value={harText}
              onChange={(e) => setHarText(e.target.value)}
              placeholder='{ "log": { "entries": [ ... ] } }'
              className="min-h-48 max-h-72 font-mono text-xs er-scroll"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handle} disabled={submitting} className="bg-accent text-accent-foreground hover:bg-accent/90">
            <Icon name="globe" size={14} aria-hidden />
            {submitting ? "Analyzing…" : "Analyze HAR"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Mark stale dialog                                                   */
/* ------------------------------------------------------------------ */

function MarkStaleDialog({
  endpoint,
  open,
  onOpenChange,
  onMarked,
}: {
  endpoint: DiscoveredEndpoint | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onMarked: () => void;
}) {
  const [reason, setReason] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) setReason("");
  }, [open]);

  if (!endpoint) return null;

  const handle = async () => {
    setSubmitting(true);
    try {
      await api.markEndpointStale(endpoint.id, reason.trim() || "Manually marked stale");
      toast.success("Endpoint marked stale", {
        description: "Future replays will skip it until it is re-discovered.",
      });
      onOpenChange(false);
      onMarked();
    } catch {
      toast.error("Could not update endpoint", { description: "Backend unreachable." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md border-border bg-card">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-heading text-lg">
            <Icon name="alert" size={16} className="text-chart-4" aria-hidden />
            Mark endpoint stale
          </DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-1">
              <p>
                Stale endpoints are excluded from the internal_route replay path
                until they are re-discovered from a fresh HAR.
              </p>
              <p className="font-mono text-xs text-foreground break-all">
                {endpoint.method} {endpoint.urlPattern}
              </p>
            </div>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <label className="er-caption text-muted-foreground" htmlFor="stale-reason">
            Reason (optional)
          </label>
          <Textarea
            id="stale-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. vendor changed the contract — returns 410 now"
            className="min-h-20"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button
            onClick={handle}
            disabled={submitting}
            className="bg-chart-4 text-background hover:bg-chart-4/90"
          >
            <Icon name="alert" size={14} aria-hidden />
            {submitting ? "Marking…" : "Mark stale"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Endpoint row                                                        */
/* ------------------------------------------------------------------ */

function EndpointRow({
  ep,
  onMarkStale,
}: {
  ep: DiscoveredEndpoint;
  onMarkStale: (ep: DiscoveredEndpoint) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const successRate =
    ep.timesReplayed > 0
      ? ep.timesSucceeded / ep.timesReplayed
      : null;

  return (
    <>
        <TableRow
          className="cursor-pointer hover:bg-secondary/40"
          onClick={() => setOpen((v) => !v)}
        >
          <TableCell>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 text-left"
                aria-label={open ? "Collapse row" : "Expand row"}
                aria-expanded={open}
              >
                <Icon
                  name={open ? "chevronDown" : "chevronRight"}
                  size={12}
                  className="text-muted-foreground"
                  aria-hidden
                />
                <span className="font-mono text-xs text-foreground truncate max-w-[16ch]">
                  {ep.actionName}
                </span>
              </button>
          </TableCell>
          <TableCell>
            <Badge className={cn("border-transparent font-mono text-[10px]", methodColor(ep.method))}>
              {ep.method}
            </Badge>
          </TableCell>
          <TableCell className="max-w-[28ch]">
            <span className="font-mono text-xs text-muted-foreground truncate block" title={ep.url}>
              {ep.url}
            </span>
          </TableCell>
          <TableCell className="w-28">
            <div className="flex items-center gap-2">
              <Progress value={ep.businessScore * 100} className="h-1.5 bg-secondary" />
              <span className="er-caption tabular-nums text-muted-foreground w-8 text-right">
                {Math.round(ep.businessScore * 100)}
              </span>
            </div>
          </TableCell>
          <TableCell>
            <Badge
              className={cn(
                "border-transparent",
                ep.status === "active" && "er-pill-success",
                ep.status === "stale" && "er-pill-warn",
                ep.status === "deprecated" && "er-pill-danger",
              )}
            >
              {ep.status}
            </Badge>
          </TableCell>
          <TableCell className="tabular-nums text-muted-foreground">
            {ep.timesReplayed}
          </TableCell>
          <TableCell className="tabular-nums">
            {successRate === null ? (
              <span className="text-muted-foreground">—</span>
            ) : (
              <span className={cn(successRate >= 0.9 ? "text-accent" : "text-chart-4")}>
                {Math.round(successRate * 100)}%
              </span>
            )}
          </TableCell>
          <TableCell className="tabular-nums text-muted-foreground">
            {ep.avgLatencyMs ? `${ep.avgLatencyMs}ms` : "—"}
          </TableCell>
          <TableCell className="er-caption text-muted-foreground">
            {timeAgo(ep.lastReplayedAt)}
          </TableCell>
          <TableCell>
            {ep.status === "active" && (
              <Button
                size="sm"
                variant="outline"
                className="rounded-full"
                onClick={(e) => {
                  e.stopPropagation();
                  onMarkStale(ep);
                }}
              >
                <Icon name="alert" size={11} aria-hidden /> Stale
              </Button>
            )}
          </TableCell>
        </TableRow>
        {open && (
          <TableRow className="bg-secondary/30 hover:bg-secondary/30">
            <TableCell colSpan={10} className="p-4">
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                <div>
                  <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1.5">
                    Body template
                  </p>
                  <CodeBlock code={prettyJson(ep.bodyTemplate)} language="json" />
                </div>
                <div>
                  <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1.5">
                    Field mapping
                  </p>
                  <CodeBlock code={prettyJson(ep.fieldMapping)} language="json" />
                </div>
                <div className="space-y-2">
                  <div>
                    <p className="er-caption text-muted-foreground uppercase tracking-wide">
                      Cookie env var
                    </p>
                    <code className="font-mono text-xs text-foreground break-all">
                      {ep.cookieEnvVar || "—"}
                    </code>
                  </div>
                  <div>
                    <p className="er-caption text-muted-foreground uppercase tracking-wide">
                      Cluster size
                    </p>
                    <span className="text-sm tabular-nums">{ep.clusterSize}</span>
                  </div>
                  <div>
                    <p className="er-caption text-muted-foreground uppercase tracking-wide">
                      Discovered from
                    </p>
                    <span className="er-caption text-muted-foreground">{ep.discoveredFrom}</span>
                  </div>
                </div>
                <div>
                  <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1.5">
                    Response shape
                  </p>
                  <CodeBlock code={prettyJson(ep.responseShape)} language="json" />
                </div>
              </div>
            </TableCell>
          </TableRow>
        )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Endpoints table                                                     */
/* ------------------------------------------------------------------ */

function EndpointsTable({
  onAnalyze,
}: {
  onAnalyze: () => void;
}) {
  const { data, loading, error, refetch } = useApi<DiscoveredEndpoint[]>(
    () => api.listDiscoveredEndpoints(),
    [],
  );
  const [staleTarget, setStaleTarget] = React.useState<DiscoveredEndpoint | null>(null);

  const list = data ?? [];

  return (
    <Card className="gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon name="link" size={14} className="text-accent" aria-hidden />
          <h3 className="er-h3">Discovered endpoints</h3>
          <Badge variant="outline" className="er-caption">
            {list.length}
          </Badge>
        </div>
        <Button size="sm" className="rounded-full" onClick={onAnalyze}>
          <Icon name="upload" size={12} aria-hidden /> Analyze HAR
        </Button>
      </div>

      {error ? (
        <EmptyState
          icon="globe"
          title="Backend connecting…"
          description="Discovered endpoints will appear here once the FastAPI service is reachable."
          action={
            <Button size="sm" variant="outline" className="rounded-full" onClick={refetch}>
              <Icon name="sync" size={14} aria-hidden /> Retry
            </Button>
          }
        />
      ) : loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          icon="globe"
          title="No endpoints discovered yet"
          description="Record a workflow to capture HAR, or analyze a HAR manually to populate the replay registry."
          action={
            <Button size="sm" className="rounded-full" onClick={onAnalyze}>
              <Icon name="upload" size={14} aria-hidden /> Analyze HAR
            </Button>
          }
        />
      ) : (
        <div className="max-h-96 overflow-y-auto er-scroll rounded-md border border-border">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead className="w-40">Action</TableHead>
                <TableHead className="w-16">Method</TableHead>
                <TableHead>URL</TableHead>
                <TableHead className="w-32">Score</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-20">Replays</TableHead>
                <TableHead className="w-24">Success</TableHead>
                <TableHead className="w-24">Latency</TableHead>
                <TableHead className="w-28">Last replay</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.map((ep) => (
                <EndpointRow
                  key={ep.id}
                  ep={ep}
                  onMarkStale={(target) => setStaleTarget(target)}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <MarkStaleDialog
        endpoint={staleTarget}
        open={staleTarget !== null}
        onOpenChange={(o) => { if (!o) setStaleTarget(null); }}
        onMarked={refetch}
      />
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* DiscoveryView                                                       */
/* ------------------------------------------------------------------ */

export function DiscoveryView() {
  const [analyzeOpen, setAnalyzeOpen] = React.useState(false);
  // refetch tick — bumping this key re-mounts EndpointsTable to refresh data
  // after a successful HAR analysis.
  const [tick, setTick] = React.useState(0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="globe"
        title="Network Discovery"
        subtitle="Internal endpoints discovered from HAR captures — replayed instead of clicking. 10x faster, 10x more reliable."
        action={
          <Button className="rounded-full" onClick={() => setAnalyzeOpen(true)}>
            <Icon name="upload" size={16} aria-hidden /> Analyze HAR
          </Button>
        }
      />
      <StatRow />
      <EndpointsTable
        key={tick}
        onAnalyze={() => setAnalyzeOpen(true)}
      />
      <AnalyzeHarDialog
        open={analyzeOpen}
        onOpenChange={setAnalyzeOpen}
        onDone={() => setTick((t) => t + 1)}
      />
    </motion.div>
  );
}

export default DiscoveryView;
