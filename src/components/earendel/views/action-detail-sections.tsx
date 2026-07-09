"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import type { Execution } from "@/lib/earendel/types";
import { StatusDot, AdapterChip, EmptyState } from "../primitives";
import { timeAgo } from "./action-detail-helpers";

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
/* Re-exports — kept here so action-detail-view.tsx imports unchanged  */
/* ------------------------------------------------------------------ */

export { ContractTab } from "./action-detail-contract";
export { ExecutionTab } from "./action-detail-execution";
export { TestsCanaryTab } from "./action-detail-tests";
export { VersionsTab } from "./action-detail-versions";
export { DependenciesTab } from "./action-detail-dependencies";
