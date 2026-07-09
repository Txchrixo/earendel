"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Icon } from "../icon";
import { api } from "@/lib/earendel/api-client";
import type {
  Execution,
  ExecutionStatus,
  AdapterType,
  TraceEvent,
  RepairProposal,
} from "@/lib/earendel/types";
import {
  AdapterChip,
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

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    month: "short",
    day: "numeric",
  });
}

export const STATUS_OPTIONS: ExecutionStatus[] = [
  "success",
  "failed",
  "degraded",
  "human_review",
  "running",
];
export const CALLER_OPTIONS = ["agent", "schedule", "manual", "canary"] as const;
export const ADAPTER_OPTIONS: AdapterType[] = [
  "api",
  "internal_route",
  "browser",
  "bu_browser",
  "vision",
  "human",
];

export const traceLevelColor: Record<TraceEvent["level"], string> = {
  info: "text-muted-foreground",
  warn: "text-chart-4",
  error: "text-destructive",
};

export function TraceTimeline({ traces }: { traces: TraceEvent[] }) {
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

export function FallbackChain({ execution }: { execution: Execution }) {
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

export function KeyValueCard({
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

/* ------------------------------------------------------------------ */
/* ProposeRepairButton — triggers LLM repair proposal for a failed run */
/* ------------------------------------------------------------------ */

export function ProposeRepairButton({
  actionId,
  executionId,
}: {
  actionId: string;
  executionId: string;
}) {
  const [loading, setLoading] = React.useState(false);
  const handle = async () => {
    setLoading(true);
    try {
      const result = await api.proposeRepair(actionId, executionId);
      if ("proposal" in result && result.proposal === null) {
        toast.error("No repair proposed", {
          description: "The failure wasn't a selector error or no candidate was found.",
        });
      } else {
        toast.success("Repair proposed", {
          description: `Confidence ${Math.round((result as RepairProposal).confidence * 100)}% — review in Monitoring.`,
        });
      }
    } catch {
      toast.error("Proposal failed", { description: "Backend unreachable." });
    } finally {
      setLoading(false);
    }
  };
  return (
    <Button size="sm" variant="outline" className="rounded-full" onClick={handle} disabled={loading}>
      <Icon name="wrench" size={12} aria-hidden />
      {loading ? "Proposing…" : "Propose repair"}
    </Button>
  );
}
