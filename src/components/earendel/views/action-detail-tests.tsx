"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import type { TypedAction } from "@/lib/earendel/types";
import { StatusDot, EmptyState } from "../primitives";
import { timeAgo } from "./action-detail-helpers";

/* ------------------------------------------------------------------ */
/* Tests & Canary tab                                                 */
/* ------------------------------------------------------------------ */

export function TestsCanaryTab({ action }: { action: TypedAction }) {
  const { refetch } = useApi(() => Promise.resolve(action), [action.id]);
  const [runningId, setRunningId] = React.useState<string | null>(null);
  const passPct = action.testsTotal > 0 ? (action.testsPassed / action.testsTotal) * 100 : 0;

  const runCanary = async (canaryId: string) => {
    setRunningId(canaryId);
    try {
      await api.runCanary(action.id);
      toast.success("Canary queued", {
        description: "Synthetic run dispatched. Results land in Monitoring.",
      });
      refetch();
    } catch {
      toast.error("Could not run canary", { description: "Backend unreachable." });
    } finally {
      setRunningId(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-3 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="checkCircle" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Test suite</h4>
          </div>
          <span className="er-caption text-muted-foreground">
            {action.testsPassed}/{action.testsTotal} passing
          </span>
        </div>
        <Progress value={passPct} className="bg-secondary" />
      </Card>

      {action.canary.length === 0 ? (
        <EmptyState
          icon="beaker"
          title="No canaries configured"
          description="Schedule a synthetic run to validate this action continuously."
        />
      ) : (
        <div className="grid gap-3">
          {action.canary.map((c) => (
            <Card key={c.id} className="gap-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Icon name="beaker" size={14} className="text-accent" aria-hidden />
                  <span className="text-sm font-medium">{c.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="er-caption text-muted-foreground">
                    <Icon name="calendar" size={11} className="mr-1 inline" aria-hidden />
                    {c.schedule}
                  </span>
                  <StatusDot
                    status={
                      c.lastStatus === "passed"
                        ? "success"
                        : c.lastStatus === "warning"
                          ? "human_review"
                          : "failed"
                    }
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-full"
                    onClick={() => runCanary(c.id)}
                    disabled={runningId === c.id}
                  >
                    <Icon name="sync" size={12} aria-hidden />
                    {runningId === c.id ? "Running…" : "Run canary now"}
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[160px]">
                  <div className="flex items-center justify-between er-caption text-muted-foreground">
                    <span>Pass rate</span>
                    <span>{Math.round(c.passRate * 100)}%</span>
                  </div>
                  <Progress value={c.passRate * 100} className="mt-1 bg-secondary" />
                </div>
                <span className="er-caption text-muted-foreground">
                  last run {timeAgo(c.lastRun)}
                </span>
              </div>
              <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {c.assertions.map((a, idx) => (
                  <li
                    key={idx}
                    className="flex items-center gap-2 rounded-md border border-border bg-secondary/40 px-2 py-1.5"
                  >
                    <Icon
                      name={a.passed ? "checkCircleFill" : "xCircleFill"}
                      size={12}
                      className={a.passed ? "text-accent" : "text-destructive"}
                      aria-hidden
                    />
                    <code className="font-mono text-xs">{a.name}</code>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </motion.div>
  );
}
