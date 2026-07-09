"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { TraceEvent } from "@/lib/earendel/types";
import { AdapterChip } from "../primitives";

/* ------------------------------------------------------------------ */
/* DiffTraceTimeline — unified diff of two trace sequences            */
/* ------------------------------------------------------------------ */

export type DiffKind = "unchanged" | "added" | "removed" | "changed";

export interface DiffRow {
  kind: DiffKind;
  original?: TraceEvent;
  replay?: TraceEvent;
}

export function traceKey(t: TraceEvent): string {
  return `${t.adapter}:${t.step ?? ""}:${t.message}`;
}

export function diffTraces(original: TraceEvent[], replay: TraceEvent[]): DiffRow[] {
  /**Compute a simple LCS-based diff of two trace sequences.

  Returns rows tagged unchanged/added/removed/changed. A pair is "changed"
  when the step matches but the message or level differs.
  */
  const rows: DiffRow[] = [];
  const seen = new Set<string>();
  const origMap = new Map(original.map((t) => [traceKey(t), t]));
  const replayMap = new Map(replay.map((t) => [traceKey(t), t]));

  // Walk original; mark removed or changed.
  for (const t of original) {
    const k = traceKey(t);
    if (replayMap.has(k)) {
      rows.push({ kind: "unchanged", original: t, replay: replayMap.get(k) });
      seen.add(k);
    } else {
      // Check if a trace with the same step but different message exists → changed.
      const sameStep = replay.find(
        (r) => r.step === t.step && r.adapter === t.adapter && !seen.has(traceKey(r)),
      );
      if (sameStep) {
        rows.push({ kind: "changed", original: t, replay: sameStep });
        seen.add(traceKey(sameStep));
      } else {
        rows.push({ kind: "removed", original: t });
      }
    }
  }
  // Walk replay; mark added.
  for (const t of replay) {
    const k = traceKey(t);
    if (!seen.has(k) && !origMap.has(k)) {
      rows.push({ kind: "added", replay: t });
      seen.add(k);
    }
  }
  return rows;
}

export const diffStyles: Record<DiffKind, { dot: string; label: string; rowBg: string; text: string }> = {
  unchanged: { dot: "bg-muted-foreground/50", label: "", rowBg: "", text: "text-foreground" },
  added: { dot: "bg-accent", label: "+", rowBg: "bg-accent/5", text: "text-accent" },
  removed: { dot: "bg-destructive", label: "−", rowBg: "bg-destructive/5", text: "text-destructive" },
  changed: { dot: "bg-chart-4", label: "~", rowBg: "bg-chart-4/5", text: "text-chart-4" },
};

export function DiffTraceTimeline({
  original,
  replay,
}: {
  original: TraceEvent[];
  replay: TraceEvent[];
}) {
  const rows = diffTraces(original, replay);
  if (rows.length === 0) {
    return (
      <p className="er-caption text-muted-foreground py-4 text-center">No trace events.</p>
    );
  }
  return (
    <ol className="er-scroll relative flex max-h-[32rem] flex-col gap-0 overflow-y-auto rounded-md border border-border">
      {rows.map((row, i) => {
        const t = row.replay ?? row.original!;
        const s = diffStyles[row.kind];
        return (
          <li
            key={i}
            className={cn(
              "relative flex items-start gap-3 border-b border-border/50 px-3 py-2 last:border-b-0",
              s.rowBg,
            )}
          >
            <span className={cn("mt-1.5 size-2.5 shrink-0 rounded-full", s.dot)} aria-hidden />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn("font-mono text-xs font-bold w-3", s.text)}>{s.label}</span>
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
              {row.kind === "changed" ? (
                <div className="mt-0.5 text-sm">
                  <p className="text-destructive line-through opacity-70">
                    {row.original?.message}
                  </p>
                  <p className="text-accent">{row.replay?.message}</p>
                </div>
              ) : (
                <p className={cn("mt-0.5 text-sm", s.text === "text-foreground" ? "text-foreground" : s.text)}>
                  {t.message}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
