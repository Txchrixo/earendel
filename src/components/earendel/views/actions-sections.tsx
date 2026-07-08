"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Icon, type ErIconName } from "../icon";
import { useStudio } from "@/lib/earendel/store";
import { RiskBadge, StatusDot, AdapterChip } from "../primitives";
import type {
  ActionStatus,
  AdapterType,
  PermissionScope,
  RiskLevel,
  TypedAction,
  WorkflowCategory,
} from "@/lib/earendel/types";

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

export const CATEGORY_ICON: Record<WorkflowCategory, ErIconName> = {
  finance: "briefcase",
  logistics: "package",
  healthcare: "law",
  ecommerce: "cloud",
  hr: "person",
  compliance: "shieldCheck",
  government: "briefcase",
  other: "gear",
};

const PERMISSION_VARIANT: Record<PermissionScope, string> = {
  read_only: "bg-secondary text-foreground",
  read_write: "bg-chart-4/25 text-foreground",
  submit: "bg-primary/30 text-foreground",
  destructive: "bg-destructive/30 text-foreground",
};

export function PermissionBadge({ scope }: { scope: PermissionScope }) {
  return (
    <Badge
      variant="outline"
      className={cn("border-transparent", PERMISSION_VARIANT[scope])}
    >
      <Icon name="key" size={12} aria-hidden /> {scope.replace("_", " ")}
    </Badge>
  );
}

const PUBLISH_ICON: Record<string, ErIconName> = {
  mcp: "robot",
  rest: "server",
  sdk: "code",
  webhook: "link",
};

export const CATEGORIES: WorkflowCategory[] = [
  "finance",
  "healthcare",
  "logistics",
  "ecommerce",
  "hr",
  "compliance",
  "government",
  "other",
];
export const STATUSES: ActionStatus[] = [
  "draft",
  "testing",
  "published",
  "degraded",
  "broken",
];
export const RISKS: RiskLevel[] = ["low", "medium", "high", "critical"];

/* ------------------------------------------------------------------ */
/* ActionCard                                                          */
/* ------------------------------------------------------------------ */

export function ActionCard({ action }: { action: TypedAction }) {
  const openAction = useStudio((s) => s.openAction);
  const catIcon = CATEGORY_ICON[action.category] ?? "gear";
  const testPct =
    action.testsTotal > 0 ? (action.testsPassed / action.testsTotal) * 100 : 0;
  const testsOk = action.testsPassed === action.testsTotal;

  return (
    <Card className="gap-3 p-4 transition-colors hover:border-primary/50">
      {/* Title row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="grid size-7 shrink-0 place-items-center rounded-md bg-secondary text-foreground">
            <Icon name={catIcon} size={14} aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="truncate font-mono text-sm font-medium">
              {action.signature}
            </p>
            <p className="er-caption text-muted-foreground">{action.category}</p>
          </div>
        </div>
        <StatusDot status={action.status} />
      </div>

      {/* Description */}
      <p className="line-clamp-2 min-h-[2.5rem] text-sm text-muted-foreground">
        {action.description}
      </p>

      {/* Risk + permission */}
      <div className="flex flex-wrap gap-1.5">
        <RiskBadge level={action.riskLevel} />
        <PermissionBadge scope={action.permissions} />
      </div>

      {/* Execution path */}
      <div>
        <p className="er-caption mb-1.5 text-muted-foreground uppercase tracking-wide">
          Execution path
        </p>
        <div className="flex flex-wrap items-center gap-1">
          {action.executionMethods.map((m, i) => (
            <React.Fragment key={m}>
              <span
                className={cn(
                  m === action.preferredAdapter &&
                    "rounded-md ring-1 ring-accent",
                )}
              >
                <AdapterChip adapter={m as AdapterType} />
              </span>
              {i < action.executionMethods.length - 1 && (
                <Icon
                  name="arrowRight"
                  size={12}
                  className="text-muted-foreground"
                  aria-hidden
                />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Tests */}
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="er-caption flex items-center gap-1 text-muted-foreground">
            <Icon name="beaker" size={12} aria-hidden /> Tests
          </span>
          <span
            className={cn(
              "er-caption tabular-nums",
              testsOk ? "text-accent" : "text-chart-4",
            )}
          >
            {action.testsPassed}/{action.testsTotal}
          </span>
        </div>
        <Progress
          value={testPct}
          className={cn(
            "h-1.5",
            testsOk
              ? "[&_[data-slot=progress-indicator]]:bg-accent"
              : "[&_[data-slot=progress-indicator]]:bg-chart-4",
          )}
        />
      </div>

      {/* Version + publish targets */}
      <div className="flex items-center justify-between border-t border-border pt-2">
        <span className="er-caption flex items-center gap-1 text-muted-foreground">
          <Icon name="versions" size={12} aria-hidden /> v{action.version}
        </span>
        <div className="flex gap-1">
          {action.publishedAs.map((p) => (
            <span
              key={p}
              className="inline-flex items-center gap-1 rounded border border-border bg-secondary px-1.5 py-0.5 er-caption text-muted-foreground"
            >
              <Icon name={PUBLISH_ICON[p] ?? "package"} size={10} aria-hidden />{" "}
              {p}
            </span>
          ))}
        </div>
      </div>

      <Button
        size="sm"
        onClick={() => openAction(action.id)}
        className="w-full"
      >
        <Icon name="arrowRight" size={14} aria-hidden /> Open action
      </Button>
    </Card>
  );
}
