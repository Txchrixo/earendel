"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Icon } from "../icon";
import type { TypedAction, AdapterType } from "@/lib/earendel/types";
import { ADAPTER_META, FALLBACK_ORDER } from "./action-detail-helpers";

/* ------------------------------------------------------------------ */
/* Execution tab — fallback chain stepper                             */
/* ------------------------------------------------------------------ */

export function ExecutionTab({ action }: { action: TypedAction }) {
  const active = new Set<AdapterType>(action.executionMethods);
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <ol className="relative flex flex-col gap-2">
        {FALLBACK_ORDER.map((adapter, i) => {
          const meta = ADAPTER_META[adapter];
          const isActive = active.has(adapter);
          const isPreferred = action.preferredAdapter === adapter;
          return (
            <li key={adapter} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    "grid size-9 place-items-center rounded-md border",
                    isActive
                      ? "border-accent bg-accent/15 text-accent"
                      : "border-border bg-secondary text-muted-foreground",
                  )}
                >
                  <Icon name={meta.icon} size={16} aria-hidden />
                </span>
                {i < FALLBACK_ORDER.length - 1 && (
                  <span className="my-1 h-full w-px flex-1 bg-border" aria-hidden />
                )}
              </div>
              <Card
                className={cn(
                  "flex-1 gap-1 p-3",
                  !isActive && "opacity-60",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{meta.name}</span>
                  <Badge variant="outline" className="er-caption">
                    step {i + 1}
                  </Badge>
                  {isPreferred && (
                    <Badge className="bg-accent text-accent-foreground">
                      <Icon name="star" size={10} aria-hidden /> Preferred
                    </Badge>
                  )}
                  {!isActive && (
                    <span className="er-caption text-muted-foreground">inactive</span>
                  )}
                </div>
                <p className="er-caption text-muted-foreground">{meta.desc}</p>
                <div className="mt-1 flex flex-wrap gap-3 er-caption text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Icon name="shieldCheck" size={11} aria-hidden /> {meta.reliability}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Icon name="clock" size={11} aria-hidden /> {meta.speed}
                  </span>
                </div>
              </Card>
            </li>
          );
        })}
      </ol>
      <Card className="gap-2 border-chart-4/30 bg-chart-4/5 p-4">
        <div className="flex items-center gap-2">
          <Icon name="shield" size={14} className="text-chart-4" aria-hidden />
          <h4 className="text-sm font-medium">Risk-gating policy</h4>
        </div>
        <p className="er-caption text-muted-foreground">
          Read-only flows execute through the chain automatically. Destructive
          and submit-level permissions pause before the final step and require a
          human authorisation token — surfaced in the Executions view as
          <span className="text-foreground"> human_review</span>.
        </p>
      </Card>
    </motion.div>
  );
}
