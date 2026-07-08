"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import type { Execution, AdapterType } from "@/lib/earendel/types";

/* ------------------------------------------------------------------ */
/* FailureBreakdown — donut chart of failures by adapter              */
/* ------------------------------------------------------------------ */

const ADAPTER_COLORS: Record<AdapterType, string> = {
  api: "#6B5876",
  internal_route: "#7A8548",
  browser: "#C9A66B",
  vision: "#8B6F5A",
  human: "#A5A19B",
};

const ADAPTER_LABELS: Record<AdapterType, string> = {
  api: "Official API",
  internal_route: "Internal route",
  browser: "Browser",
  vision: "Vision",
  human: "Human review",
};

interface BreakdownSlice {
  adapter: AdapterType;
  count: number;
  label: string;
}

export function FailureBreakdown() {
  const { data: executions, loading } = useApi<Execution[]>(
    () => api.listExecutions(),
    [],
  );

  const failed = (executions ?? []).filter(
    (e) => e.status === "failed" || e.status === "degraded" || e.status === "human_review",
  );

  // Count by the adapter that ultimately handled the (failed) execution.
  const counts = new Map<AdapterType, number>();
  for (const e of failed) {
    counts.set(e.adapter, (counts.get(e.adapter) ?? 0) + 1);
  }
  const slices: BreakdownSlice[] = Array.from(counts.entries())
    .map(([adapter, count]) => ({
      adapter,
      count,
      label: ADAPTER_LABELS[adapter],
    }))
    .sort((a, b) => b.count - a.count);

  const total = slices.reduce((sum, s) => sum + s.count, 0);

  return (
    <Card className="er-card-raised gap-3 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon name="graph" size={14} aria-hidden />
          <h3 className="er-h3">Failure breakdown</h3>
        </div>
        <span className="er-caption text-muted-foreground">
          {total} failed/degraded · by adapter
        </span>
      </div>

      {loading ? (
        <div className="flex h-48 items-center justify-center">
          <Icon name="sync" size={20} className="er-pulse text-muted-foreground" aria-hidden />
        </div>
      ) : total === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center gap-2 text-center">
          <span
            className="grid size-12 place-items-center rounded-full"
            style={{
              background: "linear-gradient(135deg, rgba(122,133,72,0.25), rgba(122,133,72,0.08))",
              color: "#7A8548",
            }}
          >
            <Icon name="checkCircle" size={24} aria-hidden />
          </span>
          <p className="font-heading text-lg">No failures</p>
          <p className="er-caption text-muted-foreground">
            All recent executions succeeded. The repair loop is idle.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_1fr]">
          {/* Donut */}
          <div className="relative h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="count"
                  nameKey="label"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={3}
                  stroke="var(--background)"
                  strokeWidth={2}
                >
                  {slices.map((s) => (
                    <Cell key={s.adapter} fill={ADAPTER_COLORS[s.adapter]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                  formatter={(v: number, _name, props) => [
                    `${v} (${Math.round((v / total) * 100)}%)`,
                    ADAPTER_LABELS[(props.payload as BreakdownSlice).adapter],
                  ]}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* Center label */}
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-heading text-3xl leading-none tabular-nums">{total}</span>
              <span className="er-caption text-muted-foreground">failures</span>
            </div>
          </div>

          {/* Legend with counts */}
          <div className="flex flex-col justify-center gap-2">
            {slices.map((s) => {
              const pct = Math.round((s.count / total) * 100);
              return (
                <div key={s.adapter} className="flex items-center gap-2.5">
                  <span
                    className="size-3 rounded-sm shrink-0"
                    style={{ background: ADAPTER_COLORS[s.adapter] }}
                    aria-hidden
                  />
                  <span className="text-sm text-foreground flex-1">{s.label}</span>
                  <span className="text-sm font-mono tabular-nums text-muted-foreground">
                    {s.count}
                  </span>
                  <Badge variant="outline" className="er-pill-neutral text-xs tabular-nums w-10 justify-center">
                    {pct}%
                  </Badge>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}

export default FailureBreakdown;
