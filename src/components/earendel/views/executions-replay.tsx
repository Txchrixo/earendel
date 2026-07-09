"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "../icon";
import type { Execution } from "@/lib/earendel/types";
import { TraceTimeline, KeyValueCard } from "./executions-helpers";
import { DiffTraceTimeline } from "./executions-diff";

/* ------------------------------------------------------------------ */
/* ReplayCompareCard — side-by-side trace diff after replay           */
/* ------------------------------------------------------------------ */

export function ReplayCompareCard({
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
    <Card className="gap-3 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="grid size-8 place-items-center rounded-md bg-secondary text-muted-foreground"
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

      {/* Unified trace diff */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="er-caption text-muted-foreground flex items-center gap-1.5">
            <Icon name="diff" size={12} aria-hidden /> Unified trace diff
          </p>
          <div className="flex items-center gap-3 er-caption">
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-muted-foreground/50" aria-hidden /> unchanged
            </span>
            <span className="flex items-center gap-1 text-accent">
              <span className="size-2 rounded-full bg-accent" aria-hidden /> added
            </span>
            <span className="flex items-center gap-1 text-destructive">
              <span className="size-2 rounded-full bg-destructive" aria-hidden /> removed
            </span>
            <span className="flex items-center gap-1 text-chart-4">
              <span className="size-2 rounded-full bg-chart-4" aria-hidden /> changed
            </span>
          </div>
        </div>
        <DiffTraceTimeline original={original.traces} replay={replay.traces} />
      </div>

      {/* Side-by-side traces (still available for reference) */}
      <details className="group">
        <summary className="er-caption text-muted-foreground cursor-pointer flex items-center gap-1.5 hover:text-foreground">
          <Icon name="chevronRight" size={12} aria-hidden className="group-open:rotate-90 transition-transform" />
          Show side-by-side traces
        </summary>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 mt-3">
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
      </details>

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
