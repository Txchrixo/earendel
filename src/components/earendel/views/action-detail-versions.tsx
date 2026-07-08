"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Icon } from "../icon";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import type {
  TypedAction,
  ActionVersion,
  ActionContract,
} from "@/lib/earendel/types";
import { AdapterChip } from "../primitives";

/* ------------------------------------------------------------------ */
/* Versions tab                                                       */
/* ------------------------------------------------------------------ */

export const versionBadge: Record<ActionVersion["status"], React.ReactNode> = {
  stable: <Badge variant="secondary">stable</Badge>,
  latest: (
    <Badge className="bg-accent text-accent-foreground">
      <Icon name="star" size={10} aria-hidden /> latest
    </Badge>
  ),
  deprecated: <Badge variant="outline">deprecated</Badge>,
  rollback: <Badge variant="destructive">rolled back</Badge>,
};

export function VersionsTab({ action }: { action: TypedAction }) {
  const [rolling, setRolling] = React.useState<string | null>(null);
  const [compareA, setCompareA] = React.useState<string | null>(null);
  const [compareB, setCompareB] = React.useState<string | null>(null);
  const setView = useStudio((s) => s.setView);

  const rollback = async (version: string) => {
    setRolling(version);
    try {
      await api.rollbackAction(action.id, version);
      toast.success("Rolled back", {
        description: `${action.name} now serves v${version}.`,
      });
      setView("actions");
    } catch {
      toast.error("Rollback failed", { description: "Backend unreachable." });
    } finally {
      setRolling(null);
    }
  };

  const versions = [...action.versions].sort((a, b) =>
    new Date(b.releasedAt).getTime() - new Date(a.releasedAt).getTime(),
  );

  const versionA = versions.find((v) => v.version === compareA);
  const versionB = versions.find((v) => v.version === compareB);
  const showDiff = versionA && versionB;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-3"
    >
      {showDiff && (
        <VersionDiffCard a={versionA!} b={versionB!} onClose={() => { setCompareA(null); setCompareB(null); }} />
      )}
      {versions.map((v, i) => {
        const isCurrent = v.version === action.version;
        const canRollback = v.status === "stable" && !isCurrent;
        const isSelectedA = compareA === v.version;
        const isSelectedB = compareB === v.version;
        return (
          <Card
            key={v.version}
            className={cn(
              "gap-2 p-4 transition-colors",
              isCurrent && "border-accent",
              isSelectedA && "ring-1 ring-chart-2",
              isSelectedB && "ring-1 ring-chart-4",
            )}
          >
            <div className="flex flex-wrap items-center gap-3">
              <span
                className="grid size-8 place-items-center rounded-md bg-secondary text-muted-foreground font-mono text-xs font-bold"
              >
                v{v.version}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{v.changelog}</span>
                  {isCurrent && (
                    <Badge className="er-pill-success">current</Badge>
                  )}
                  {versionBadge[v.status]}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-3 er-caption text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Icon name="calendar" size={11} aria-hidden />{" "}
                    {new Date(v.releasedAt).toLocaleDateString()}
                  </span>
                  <AdapterChip adapter={v.adapter} />
                  <span className="inline-flex items-center gap-1">
                    <Icon name="meter" size={11} aria-hidden />{" "}
                    {Math.round(v.successRate * 100)}% success
                  </span>
                </div>
              </div>
              {/* Compare selectors */}
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant={isSelectedA ? "default" : "ghost"}
                  className={cn("rounded-full", isSelectedA ? "bg-chart-2 text-background" : "")}
                  onClick={() => setCompareA(isSelectedA ? null : v.version)}
                  aria-pressed={isSelectedA}
                  title="Set as version A for comparison"
                >
                  A
                </Button>
                <Button
                  size="sm"
                  variant={isSelectedB ? "default" : "ghost"}
                  className={cn("rounded-full", isSelectedB ? "bg-chart-4 text-background" : "")}
                  onClick={() => setCompareB(isSelectedB ? null : v.version)}
                  aria-pressed={isSelectedB}
                  title="Set as version B for comparison"
                >
                  B
                </Button>
              </div>
              {canRollback && (
                <Button
                  size="sm"
                  variant="outline"
                  className="rounded-full"
                  onClick={() => rollback(v.version)}
                  disabled={rolling === v.version}
                >
                  <Icon name="history" size={12} aria-hidden />
                  {rolling === v.version ? "Rolling back…" : "Rollback"}
                </Button>
              )}
            </div>
            {i < versions.length - 1 && <div className="h-px bg-border" aria-hidden />}
          </Card>
        );
      })}
      {!showDiff && versions.length >= 2 && (
        <p className="er-caption text-muted-foreground text-center pt-2">
          <Icon name="lightbulb" size={12} aria-hidden className="inline mr-1" />
          Pick two versions (A + B) to compare what changed.
        </p>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* VersionDiffCard — diff between two ActionVersions                  */
/* ------------------------------------------------------------------ */

export function VersionDiffCard({
  a,
  b,
  onClose,
}: {
  a: ActionVersion;
  b: ActionVersion;
  onClose: () => void;
}) {
  const adapterChanged = a.adapter !== b.adapter;
  const successDelta = b.successRate - a.successRate;
  const successImproved = successDelta > 0;
  const dateDelta =
    (new Date(b.releasedAt).getTime() - new Date(a.releasedAt).getTime()) / 86400000;

  return (
    <Card className="gap-3 p-5 border-accent/40">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground"
          >
            <Icon name="diff" size={16} aria-hidden />
          </span>
          <div>
            <h4 className="text-sm font-medium">Version comparison</h4>
            <p className="er-caption text-muted-foreground">
              v{a.version} → v{b.version}
            </p>
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close comparison">
          <Icon name="x" size={14} aria-hidden />
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {/* Changelog diff */}
        <div className="w-full rounded-md border border-border bg-background/40 p-3">
          <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1.5">
            Changelog
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <p className="er-caption text-chart-2 mb-0.5">v{a.version}</p>
              <p className="text-sm text-foreground">{a.changelog}</p>
            </div>
            <div>
              <p className="er-caption text-chart-4 mb-0.5">v{b.version}</p>
              <p className="text-sm text-foreground">{b.changelog}</p>
            </div>
          </div>
        </div>

        {/* Metrics diff */}
        <div
          className={cn(
            "rounded-md border px-3 py-2 text-xs",
            adapterChanged ? "er-pill-warn border-transparent" : "border-border bg-secondary text-muted-foreground",
          )}
        >
          <span className="text-muted-foreground">adapter: </span>
          {adapterChanged ? (
            <span className="font-mono">
              <span className="text-chart-2">{a.adapter.replace("_", " ")}</span>
              <Icon name="arrowRight" size={10} className="mx-1 inline" aria-hidden />
              <span className="text-chart-4">{b.adapter.replace("_", " ")}</span>
            </span>
          ) : (
            <span className="font-mono text-foreground">{a.adapter.replace("_", " ")}</span>
          )}
        </div>

        <div
          className={cn(
            "rounded-md border px-3 py-2 text-xs",
            Math.abs(successDelta) > 0.01
              ? successImproved ? "er-pill-success border-transparent" : "er-pill-danger border-transparent"
              : "border-border bg-secondary text-muted-foreground",
          )}
        >
          <span className="text-muted-foreground">success rate: </span>
          <span className="font-mono text-foreground">
            {Math.round(a.successRate * 100)}%
            <Icon name="arrowRight" size={10} className="mx-1 inline" aria-hidden />
            {Math.round(b.successRate * 100)}%
            {Math.abs(successDelta) > 0.01 && (
              <span className={successImproved ? "text-accent" : "text-destructive"}>
                {" "}({successImproved ? "+" : ""}{Math.round(successDelta * 100)}%)
              </span>
            )}
          </span>
        </div>

        <div className="rounded-md border border-border bg-secondary px-3 py-2 text-xs text-muted-foreground">
          <span>released: </span>
          <span className="font-mono text-foreground">
            {new Date(a.releasedAt).toLocaleDateString()}
            <Icon name="arrowRight" size={10} className="mx-1 inline" aria-hidden />
            {new Date(b.releasedAt).toLocaleDateString()}
            {Math.abs(dateDelta) >= 1 && (
              <span className="text-muted-foreground"> ({dateDelta >= 0 ? "+" : ""}{Math.round(dateDelta)}d)</span>
            )}
          </span>
        </div>
      </div>

      {/* Contract diff (inputs/outputs) */}
      {a.contractSnapshot && b.contractSnapshot && (
        <ContractDiff a={a.contractSnapshot} b={b.contractSnapshot} />
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* ContractDiff — inputs/outputs field diff between two contracts      */
/* ------------------------------------------------------------------ */

export function fieldKey(f: { name: string }): string {
  return f.name;
}

export function ContractDiff({
  a,
  b,
}: {
  a: ActionContract;
  b: ActionContract;
}) {
  const aInputs = new Map(a.inputs.map((f) => [fieldKey(f), f]));
  const bInputs = new Map(b.inputs.map((f) => [fieldKey(f), f]));
  const aOutputs = new Map(a.outputs.map((f) => [fieldKey(f), f]));
  const bOutputs = new Map(b.outputs.map((f) => [fieldKey(f), f]));

  const inputAdded = b.inputs.filter((f) => !aInputs.has(fieldKey(f)));
  const inputRemoved = a.inputs.filter((f) => !bInputs.has(fieldKey(f)));
  const outputAdded = b.outputs.filter((f) => !aOutputs.has(fieldKey(f)));
  const outputRemoved = a.outputs.filter((f) => !bOutputs.has(fieldKey(f)));

  const hasChanges =
    inputAdded.length > 0 ||
    inputRemoved.length > 0 ||
    outputAdded.length > 0 ||
    outputRemoved.length > 0;

  if (!hasChanges) return null;

  return (
    <div className="w-full rounded-md border border-border bg-background/40 p-3">
      <p className="er-caption text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1.5">
        <Icon name="diff" size={11} aria-hidden /> Contract diff
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Inputs diff */}
        <div>
          <p className="er-caption text-muted-foreground mb-1">Inputs</p>
          {inputAdded.length === 0 && inputRemoved.length === 0 ? (
            <p className="er-caption text-muted-foreground/60">unchanged</p>
          ) : (
            <div className="flex flex-col gap-1">
              {inputAdded.map((f) => (
                <div key={`+i${f.name}`} className="flex items-center gap-1.5 er-pill-success rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">+</span>
                  <code className="font-mono">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
              {inputRemoved.map((f) => (
                <div key={`-i${f.name}`} className="flex items-center gap-1.5 er-pill-danger rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">−</span>
                  <code className="font-mono line-through">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {/* Outputs diff */}
        <div>
          <p className="er-caption text-muted-foreground mb-1">Outputs</p>
          {outputAdded.length === 0 && outputRemoved.length === 0 ? (
            <p className="er-caption text-muted-foreground/60">unchanged</p>
          ) : (
            <div className="flex flex-col gap-1">
              {outputAdded.map((f) => (
                <div key={`+o${f.name}`} className="flex items-center gap-1.5 er-pill-success rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">+</span>
                  <code className="font-mono">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
              {outputRemoved.map((f) => (
                <div key={`-o${f.name}`} className="flex items-center gap-1.5 er-pill-danger rounded px-2 py-0.5 text-xs">
                  <span className="font-mono font-bold">−</span>
                  <code className="font-mono line-through">{f.name}</code>
                  <span className="text-muted-foreground">({f.type})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
