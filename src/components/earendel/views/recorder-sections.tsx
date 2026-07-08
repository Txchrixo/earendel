"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Icon, type ErIconName } from "../icon";
import { StatCard } from "../primitives";
import type { CapturedStep, Connector } from "@/lib/earendel/types";

/* ------------------------------------------------------------------ */
/* Step type → icon                                                    */
/* ------------------------------------------------------------------ */

export const STEP_ICON: Record<CapturedStep["type"], ErIconName> = {
  navigate: "globe",
  click: "dotFill",
  input: "code",
  select: "code",
  download: "download",
  wait: "clock",
  assert: "check",
};

/* ------------------------------------------------------------------ */
/* Seeded simulation — a realistic downloadInvoice flow                */
/* ------------------------------------------------------------------ */

export function buildSimulation(connector: Connector | undefined): CapturedStep[] {
  const domain = connector?.targetDomain ?? "supplier-portal.acme.com";
  return [
    {
      index: 0,
      type: "navigate",
      description: `Open https://${domain}`,
      url: `https://${domain}`,
      networkCalls: 3,
      screenshot: true,
      durationMs: 520,
    },
    {
      index: 1,
      type: "input",
      description: "Enter username",
      selector: "input[name=\"email\"]",
      value: "ap_user@acme.com",
      networkCalls: 0,
      screenshot: false,
      durationMs: 80,
    },
    {
      index: 2,
      type: "input",
      description: "Enter password",
      selector: "input[name=\"password\"]",
      value: "••••••••",
      networkCalls: 0,
      screenshot: false,
      durationMs: 70,
    },
    {
      index: 3,
      type: "click",
      description: "Submit login",
      selector: "button[type=\"submit\"]",
      networkCalls: 2,
      screenshot: true,
      durationMs: 410,
    },
    {
      index: 4,
      type: "navigate",
      description: "Open invoices page",
      url: `https://${domain}/invoices`,
      networkCalls: 4,
      screenshot: true,
      durationMs: 340,
    },
    {
      index: 5,
      type: "input",
      description: "Search invoice id",
      selector: "input[placeholder=\"Search invoices\"]",
      value: "{{invoiceId}}",
      networkCalls: 1,
      screenshot: false,
      durationMs: 110,
    },
    {
      index: 6,
      type: "download",
      description: "Download invoice PDF",
      selector: "a[data-invoice-download]",
      networkCalls: 2,
      screenshot: true,
      durationMs: 680,
    },
  ];
}

/* ------------------------------------------------------------------ */
/* StepRow                                                             */
/* ------------------------------------------------------------------ */

export function StepRow({ step }: { step: CapturedStep }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid grid-cols-[1.75rem_1fr_auto] items-center gap-3 rounded-md border border-border bg-background/40 px-3 py-2"
    >
      <span className="er-caption text-muted-foreground tabular-nums">
        {step.index}
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Icon
            name={STEP_ICON[step.type]}
            size={14}
            className="text-accent shrink-0"
            aria-hidden
          />
          <span className="truncate text-sm font-medium">
            {step.description}
          </span>
          {step.screenshot && (
            <Badge
              variant="outline"
              className="border-transparent bg-secondary"
            >
              <Icon name="browser" size={10} aria-hidden /> shot
            </Badge>
          )}
        </div>
        {step.selector && (
          <p className="er-caption mt-0.5 truncate font-mono text-muted-foreground">
            {step.selector}
          </p>
        )}
      </div>
      <div className="flex items-center gap-3 text-right">
        <span className="er-caption text-muted-foreground">
          <Icon name="server" size={10} aria-hidden /> {step.networkCalls ?? 0}
        </span>
        <span className="er-caption font-mono text-muted-foreground tabular-nums">
          {step.durationMs}ms
        </span>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* CapturedStepsPanel — live stat strip + captured steps list          */
/* ------------------------------------------------------------------ */

export function CapturedStepsPanel({
  revealed,
  recording,
}: {
  revealed: CapturedStep[];
  recording: boolean;
}) {
  const totalNet = revealed.reduce((s, x) => s + (x.networkCalls ?? 0), 0);
  const totalShots = revealed.filter((x) => x.screenshot).length;
  const domMutations = revealed.length * 4 + totalNet;
  const harCaptured = revealed.length >= 1;

  return (
    <>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <StatCard icon="tasklist" label="Steps" value={revealed.length} />
        <StatCard icon="server" label="Network" value={totalNet} />
        <StatCard icon="code" label="DOM mut." value={domMutations} />
        <StatCard icon="browser" label="Screenshots" value={totalShots} />
        <StatCard icon="download" label="HAR" value={harCaptured ? "yes" : "—"} />
      </div>

      <Card className="gap-2 p-3">
        <div className="flex items-center justify-between px-1">
          <p className="er-caption text-muted-foreground uppercase tracking-wide">
            Captured steps
          </p>
          {recording && (
            <span className="er-caption er-pulse text-accent">● live</span>
          )}
        </div>
        <div className="er-scroll max-h-96 space-y-2 overflow-y-auto pr-1">
          <AnimatePresence initial={false}>
            {revealed.map((s) => (
              <StepRow key={s.index} step={s} />
            ))}
          </AnimatePresence>
          {revealed.length === 0 && !recording && (
            <p className="er-caption py-6 text-center text-muted-foreground">
              Press record to start capturing.
            </p>
          )}
        </div>
      </Card>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Faux browser window                                                 */
/* ------------------------------------------------------------------ */

export function FauxBrowser({ connector }: { connector?: Connector }) {
  const domain = connector?.targetDomain ?? "supplier-portal.acme.com";
  return (
    <Card className="gap-0 overflow-hidden p-0">
      <div className="flex items-center gap-2 border-b border-border bg-secondary/40 px-3 py-2">
        <span className="size-2.5 rounded-full bg-destructive/70" aria-hidden />
        <span className="size-2.5 rounded-full bg-chart-4/70" aria-hidden />
        <span className="size-2.5 rounded-full bg-accent/70" aria-hidden />
        <div className="ml-2 flex flex-1 items-center gap-1.5 rounded border border-border bg-background/60 px-2 py-1">
          <Icon name="lock" size={12} className="text-accent" aria-hidden />
          <span className="er-caption truncate font-mono">{domain}</span>
        </div>
      </div>
      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className="border-transparent bg-accent text-accent-foreground">
            <Icon name="shieldCheck" size={12} aria-hidden /> Secure session
          </Badge>
          <Badge variant="outline" className="border-border">
            <Icon name="eye" size={12} aria-hidden /> Read-only
          </Badge>
          <Badge variant="outline" className="border-border">
            <Icon name="key" size={12} aria-hidden />{" "}
            {connector?.authMethod ?? "password"}
          </Badge>
        </div>
        <div className="space-y-1.5">
          <p className="er-caption text-muted-foreground uppercase tracking-wide">
            Allowed domains
          </p>
          <div className="flex flex-wrap gap-1">
            {(connector?.allowedDomains ?? [domain]).map((d) => (
              <span
                key={d}
                className="inline-flex items-center gap-1 rounded border border-border bg-background/40 px-1.5 py-0.5 font-mono er-caption text-muted-foreground"
              >
                <Icon name="link" size={10} aria-hidden /> {d}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Capture explainer + best practices                                  */
/* ------------------------------------------------------------------ */

const CAPTURED_SIGNALS: { icon: ErIconName; label: string; desc: string }[] = [
  { icon: "code", label: "DOM snapshot", desc: "Full HTML tree at every step." },
  {
    icon: "graph",
    label: "Accessibility tree",
    desc: "ARIA roles + names for stable selectors.",
  },
  { icon: "browser", label: "Screenshots", desc: "Full-page capture per step." },
  {
    icon: "server",
    label: "Network traffic (HAR)",
    desc: "Every XHR, fetch, redirect.",
  },
  {
    icon: "key",
    label: "Cookies & session",
    desc: "Cookie jars scoped to allowed domains.",
  },
  {
    icon: "arrowDown",
    label: "Inputs & outputs",
    desc: "Form values + extracted results.",
  },
  {
    icon: "dotFill",
    label: "Clicks / forms / nav",
    desc: "Every interaction with the target.",
  },
];

const BEST_PRACTICES = [
  "Use a dedicated service account — never your personal login.",
  "Record the cleanest happy path first; edge cases later.",
  "Pause before clicking sensitive buttons (destructive actions).",
  "Confirm postconditions visibly (PDF downloaded, status shown).",
  "Avoid noise: don't hover, scroll, or click unrelated UI.",
];

export function CaptureExplainer() {
  const [open, setOpen] = React.useState(false);
  return (
    <Card className="gap-3 p-5">
      <div>
        <h3 className="font-heading text-xl">What we capture</h3>
        <p className="er-caption mt-1 text-muted-foreground">
          Every signal needed to compile a reliable typed action.
        </p>
      </div>
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {CAPTURED_SIGNALS.map((s) => (
          <li
            key={s.label}
            className="flex items-start gap-2 rounded-md border border-border bg-background/30 p-2.5"
          >
            <span className="grid size-6 shrink-0 place-items-center rounded bg-secondary text-foreground">
              <Icon name={s.icon} size={12} aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium">{s.label}</p>
              <p className="er-caption text-muted-foreground">{s.desc}</p>
            </div>
          </li>
        ))}
      </ul>
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="w-full justify-between">
            <span className="inline-flex items-center gap-1.5">
              <Icon name="lightbulb" size={14} aria-hidden /> Recording best
              practices
            </span>
            <Icon
              name={open ? "chevronUp" : "chevronDown"}
              size={14}
              aria-hidden
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <ul className="mt-2 space-y-1.5">
            {BEST_PRACTICES.map((b, i) => (
              <li
                key={i}
                className="er-caption flex items-start gap-2 text-muted-foreground"
              >
                <Icon
                  name="check"
                  size={12}
                  className={cn("mt-0.5 shrink-0 text-accent")}
                  aria-hidden
                />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
