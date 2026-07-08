"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type ErIconName } from "./icon";
import type {
  RiskLevel,
  ActionStatus,
  ExecutionStatus,
  AdapterType,
} from "@/lib/earendel/types";

/* ------------------------------------------------------------------ */
/* StatCard                                                           */
/* ------------------------------------------------------------------ */

interface StatCardProps {
  icon: ErIconName;
  label: string;
  value: React.ReactNode;
  delta?: string;
  trend?: "up" | "down" | "flat";
  loading?: boolean;
}

const trendColor: Record<NonNullable<StatCardProps["trend"]>, string> = {
  up: "text-accent",
  down: "text-destructive",
  flat: "text-muted-foreground",
};

export function StatCard({
  icon,
  label,
  value,
  delta,
  trend = "flat",
  loading,
}: StatCardProps) {
  return (
    <Card className="gap-0 p-4">
      <div className="flex items-start justify-between">
        <span className="er-caption text-muted-foreground uppercase tracking-wide">
          {label}
        </span>
        <span className="grid size-7 place-items-center rounded-md bg-secondary text-foreground">
          <Icon name={icon} size={16} aria-hidden />
        </span>
      </div>
      <div className="mt-3 font-heading text-3xl leading-none">
        {loading ? <span className="er-pulse text-muted-foreground">…</span> : value}
      </div>
      {delta && (
        <div className={cn("er-caption mt-2", trendColor[trend])}>
          {trend === "up" ? "▲" : trend === "down" ? "▼" : "•"} {delta}
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* SectionTitle                                                       */
/* ------------------------------------------------------------------ */

interface SectionTitleProps {
  icon: ErIconName;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export function SectionTitle({ icon, title, subtitle, action }: SectionTitleProps) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div className="flex items-center gap-3">
        <span className="grid size-8 place-items-center rounded-md bg-secondary text-foreground">
          <Icon name={icon} size={16} aria-hidden />
        </span>
        <div>
          <h2 className="er-h2 leading-tight">{title}</h2>
          {subtitle && (
            <p className="er-caption text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* RiskBadge                                                          */
/* ------------------------------------------------------------------ */

const riskVariants = cva("border-transparent", {
  variants: {
    level: {
      low: "bg-accent text-accent-foreground",
      medium: "bg-chart-4 text-background",
      high: "bg-chart-5 text-foreground",
      critical: "bg-destructive text-white",
    },
  },
  defaultVariants: { level: "low" },
});

export function RiskBadge({
  level,
  className,
}: { level: RiskLevel } & VariantProps<typeof riskVariants> &
  React.ComponentProps<typeof Badge>) {
  return (
    <Badge className={cn(riskVariants({ level }), className)}>
      <Icon name="shield" size={12} aria-hidden /> {level}
    </Badge>
  );
}

/* ------------------------------------------------------------------ */
/* StatusDot                                                          */
/* ------------------------------------------------------------------ */

type AnyStatus = ActionStatus | ExecutionStatus | "active" | "paused" | "error";

const statusMap: Record<string, { color: string; label: string }> = {
  draft: { color: "bg-muted-foreground", label: "Draft" },
  testing: { color: "bg-chart-4", label: "Testing" },
  published: { color: "bg-accent", label: "Published" },
  degraded: { color: "bg-chart-5", label: "Degraded" },
  broken: { color: "bg-destructive", label: "Broken" },
  queued: { color: "bg-muted-foreground", label: "Queued" },
  running: { color: "bg-primary", label: "Running" },
  success: { color: "bg-accent", label: "Success" },
  failed: { color: "bg-destructive", label: "Failed" },
  human_review: { color: "bg-chart-4", label: "Human review" },
  active: { color: "bg-accent", label: "Active" },
  paused: { color: "bg-muted-foreground", label: "Paused" },
  error: { color: "bg-destructive", label: "Error" },
};

export function StatusDot({ status }: { status: AnyStatus }) {
  const cfg = statusMap[status] ?? { color: "bg-muted-foreground", label: status };
  return (
    <span className="inline-flex items-center gap-1.5 er-caption text-muted-foreground">
      <span
        className={cn(
          "size-2 rounded-full",
          cfg.color,
          status === "running" && "er-pulse",
        )}
        aria-hidden
      />
      {cfg.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* AdapterChip                                                        */
/* ------------------------------------------------------------------ */

const adapterIcon: Record<AdapterType, ErIconName> = {
  api: "server",
  internal_route: "link",
  browser: "browser",
  vision: "eye",
  human: "person",
};

export function AdapterChip({ adapter }: { adapter: AdapterType }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 er-caption">
      <Icon name={adapterIcon[adapter]} size={12} aria-hidden />
      {adapter.replace("_", " ")}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* EmptyState                                                         */
/* ------------------------------------------------------------------ */

interface EmptyStateProps {
  icon: ErIconName;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border bg-card/40 p-8 text-center">
      <span className="grid size-10 place-items-center rounded-md bg-secondary text-muted-foreground">
        <Icon name={icon} size={20} aria-hidden />
      </span>
      <div>
        <p className="font-heading text-lg">{title}</p>
        {description && (
          <p className="er-caption mt-1 text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* CodeBlock                                                          */
/* ------------------------------------------------------------------ */

export function CodeBlock({
  code,
  language,
}: {
  code: string;
  language?: string;
}) {
  const [copied, setCopied] = React.useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <div className="relative rounded-md border border-border bg-background/60">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="er-caption text-muted-foreground uppercase tracking-wide">
          {language ?? "code"}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={copy}
          aria-label="Copy code to clipboard"
        >
          <Icon name={copied ? "check" : "copy"} size={14} aria-hidden />
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="er-scroll max-h-80 overflow-auto p-3 text-xs leading-relaxed">
        <code className="font-mono">{code}</code>
      </pre>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Kbd                                                                */
/* ------------------------------------------------------------------ */

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-border bg-secondary px-1.5 font-mono text-[11px] text-muted-foreground">
      {children}
    </kbd>
  );
}
