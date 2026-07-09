"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Icon } from "../icon";
import type { RepairProposal } from "@/lib/earendel/types";

/* ------------------------------------------------------------------ */
/* SelectorDiff — parses two CSS selectors and highlights what changed */
/* ------------------------------------------------------------------ */

interface ParsedSelector {
  tag: string;
  id?: string;
  classes: string[];
  attributes: { name: string; value?: string; op?: string }[];
  ariaLabel?: string;
  testId?: string;
  raw: string;
}

function parseSelector(sel: string): ParsedSelector {
  const cleaned = sel.trim();
  const tagMatch = cleaned.match(/^([a-zA-Z][\w-]*)/);
  const tag = tagMatch ? tagMatch[1] : "*";
  const idMatch = cleaned.match(/#([\w-]+)/);
  const classMatches = [...cleaned.matchAll(/\.([\w-]+)/g)].map((m) => m[1]);
  const attrMatches = [...cleaned.matchAll(/\[([^\]=]+)(?:([~|^$*]?=)"?([^\]"]*)"?)?\]/g)];
  const attributes = attrMatches.map((m) => ({
    name: m[1],
    op: m[2],
    value: m[3],
  }));
  const ariaAttr = attributes.find((a) => a.name === "aria-label");
  const testIdAttr = attributes.find((a) => a.name === "data-testid" || a.name === "data-test");
  return {
    tag,
    id: idMatch ? idMatch[1] : undefined,
    classes: classMatches,
    attributes,
    ariaLabel: ariaAttr?.value,
    testId: testIdAttr?.value,
    raw: cleaned,
  };
}

function DiffPill({
  label,
  oldVal,
  newVal,
}: {
  label: string;
  oldVal?: string;
  newVal?: string;
}) {
  const changed = oldVal !== newVal;
  return (
    <div
      className={cn(
        "rounded-md border px-2.5 py-1.5 text-xs",
        changed
          ? "er-pill-warn border-transparent"
          : "border-border bg-secondary text-muted-foreground",
      )}
    >
      <span className="text-muted-foreground">{label}: </span>
      {changed ? (
        <span className="font-mono">
          <span className="line-through opacity-60">{oldVal || "—"}</span>
          <Icon name="arrowRight" size={10} className="mx-1 inline" aria-hidden />
          <span className="text-foreground font-medium">{newVal || "—"}</span>
        </span>
      ) : (
        <span className="font-mono text-foreground">{oldVal || "—"}</span>
      )}
    </div>
  );
}

export function SelectorDiff({
  failed,
  candidate,
}: {
  failed: string;
  candidate: string;
}) {
  const old = parseSelector(failed);
  const next = parseSelector(candidate);

  return (
    <div className="rounded-md border border-border bg-background/40 p-3">
      <p className="er-caption text-muted-foreground uppercase tracking-wide mb-2">
        Selector breakdown
      </p>
      <div className="flex flex-wrap gap-1.5">
        <DiffPill label="tag" oldVal={old.tag} newVal={next.tag} />
        {old.id || next.id ? (
          <DiffPill label="id" oldVal={old.id} newVal={next.id} />
        ) : null}
        {old.classes.join(".") !== next.classes.join(".") && (
          <DiffPill
            label="class"
            oldVal={old.classes.join(".") || undefined}
            newVal={next.classes.join(".") || undefined}
          />
        )}
        {old.ariaLabel !== next.ariaLabel && (
          <DiffPill label="aria-label" oldVal={old.ariaLabel} newVal={next.ariaLabel} />
        )}
        {old.testId !== next.testId && (
          <DiffPill label="data-testid" oldVal={old.testId} newVal={next.testId} />
        )}
        {/* Attribute count diff */}
        {old.attributes.length !== next.attributes.length && (
          <DiffPill
            label="attrs"
            oldVal={String(old.attributes.length)}
            newVal={String(next.attributes.length)}
          />
        )}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2">
          <p className="er-caption text-destructive mb-1 flex items-center gap-1">
            <Icon name="x" size={10} aria-hidden /> Failed
          </p>
          <code className="font-mono text-xs text-foreground break-all">{failed}</code>
        </div>
        <div className="rounded-md border border-accent/30 bg-accent/10 p-2">
          <p className="er-caption text-accent mb-1 flex items-center gap-1">
            <Icon name="check" size={10} aria-hidden /> Candidate
          </p>
          <code className="font-mono text-xs text-foreground break-all">{candidate}</code>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* RepairApprovalDialog — review + approve/reject with full context    */
/* ------------------------------------------------------------------ */

export function RepairApprovalDialog({
  proposal,
  open,
  onOpenChange,
  onResolve,
}: {
  proposal: RepairProposal | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onResolve: (id: string, decision: "approved" | "rejected") => void;
}) {
  if (!proposal) return null;
  const r = proposal;
  const autoApply = r.confidence >= 0.9;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl border-border bg-card">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-heading text-xl">
            <span
              className="grid size-8 place-items-center rounded-md bg-secondary text-muted-foreground"
            >
              <Icon name="wrench" size={16} aria-hidden />
            </span>
            Review repair proposal
          </DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-3 text-muted-foreground">
              <p>
                A canary detected selector drift on{" "}
                <code className="font-mono text-foreground">{r.actionId.slice(0, 16)}…</code>{" "}
                (v{r.actionVersion}). Review the proposed patch below.
              </p>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {/* Confidence + auto-apply hint */}
          <div className="flex items-center justify-between rounded-md border border-border bg-background/40 p-3">
            <div>
              <p className="er-caption text-muted-foreground">Confidence</p>
              <p className="font-heading text-2xl text-foreground">
                {Math.round(r.confidence * 100)}%
              </p>
            </div>
            <div className="text-right">
              {autoApply ? (
                <Badge className="er-pill-success">
                  <Icon name="checkCircle" size={12} aria-hidden /> eligible for auto-apply
                </Badge>
              ) : (
                <Badge className="er-pill-warn">
                  <Icon name="alert" size={12} aria-hidden /> manual review recommended
                </Badge>
              )}
              <p className="er-caption text-muted-foreground mt-1">
                threshold: 90% for auto-apply
              </p>
            </div>
          </div>

          {/* Reasoning */}
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1">
              LLM reasoning
            </p>
            <p className="text-sm text-foreground">{r.reason}</p>
          </div>

          {/* Selector diff */}
          <SelectorDiff failed={r.failedSelector} candidate={r.candidateSelector} />

          {/* Impact */}
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1">
              Patch impact
            </p>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li className="flex items-center gap-2">
                <Icon name="versions" size={12} aria-hidden className="text-accent" />
                Bumps patch version (e.g. 1.2.0 → 1.2.1)
              </li>
              <li className="flex items-center gap-2">
                <Icon name="history" size={12} aria-hidden className="text-accent" />
                Previous version retained for rollback
              </li>
              <li className="flex items-center gap-2">
                <Icon name="tasklist" size={12} aria-hidden className="text-accent" />
                Canary re-runs automatically after patch
              </li>
              <li className="flex items-center gap-2">
                <Icon name="shield" size={12} aria-hidden className="text-accent" />
                Audit trail records the approver + timestamp
              </li>
            </ul>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              onResolve(r.id, "rejected");
              onOpenChange(false);
            }}
          >
            <Icon name="x" size={14} aria-hidden /> Reject
          </Button>
          <Button
            onClick={() => {
              onResolve(r.id, "approved");
              onOpenChange(false);
            }}
            className="bg-accent text-accent-foreground hover:bg-accent/90"
          >
            <Icon name="check" size={14} aria-hidden /> Approve &amp; patch
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default SelectorDiff;
