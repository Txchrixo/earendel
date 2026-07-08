"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Icon, type ErIconName } from "../icon";
import { useApi, useApiMutation } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import { useStudio } from "@/lib/earendel/store";
import { SectionTitle, EmptyState, StatusDot } from "../primitives";
import { toast } from "sonner";
import type { Recording, CapturedStep, Connector } from "@/lib/earendel/types";

const STEP_ICON: Record<CapturedStep["type"], ErIconName> = {
  navigate: "globe",
  click: "dotFill",
  input: "code",
  select: "code",
  download: "download",
  wait: "clock",
  assert: "check",
};

/**
 * RecordingDetailView — inspect a captured recording: steps, signals,
 * compile status, and the action it compiled into (if any).
 */
export function RecordingDetailView() {
  const id = useStudio((s) => s.selectedRecordingId);
  const setView = useStudio((s) => s.setView);
  const openAction = useStudio((s) => s.openAction);

  const { data: recording, loading, error } = useApi<Recording>(
    () => (id ? api.getRecording(id) : Promise.reject(new Error("no id"))),
    [id],
  );

  const { data: connector } = useApi<Connector>(
    () =>
      recording
        ? api.getConnector(recording.connectorId)
        : Promise.reject(new Error("no recording")),
    [recording?.connectorId],
  );

  const compileMut = useApiMutation(
    (recId: string) => api.compileRecording(recId),
  );

  const handleCompile = async () => {
    if (!recording) return;
    try {
      const result = await compileMut.mutate(recording.id);
      toast.success("Compiled to typed action", {
        description: result.action.name,
      });
      openAction(result.action.id);
    } catch {
      toast.error("Compile failed", { description: "Backend unreachable." });
    }
  };

  if (!id) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6 md:p-8">
        <EmptyState
          icon="recorder"
          spot="recorder"
          title="No recording selected"
          description="Recordings appear here after you capture a workflow."
        />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6 md:p-8">
        <Skeleton className="h-8 w-48" />
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      </div>
    );
  }

  if (error || !recording) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6 md:p-8">
        <EmptyState icon="alert" title="Recording not found" description={error?.message} />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mx-auto w-full max-w-5xl p-6 md:p-8"
    >
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setView("recorder")}
            aria-label="Back to recorder"
          >
            <Icon name="chevronLeft" size={18} aria-hidden />
          </Button>
          <span
            className="grid size-12 place-items-center rounded-md bg-primary text-primary-foreground"
          >
            <Icon name="recorder" size={24} aria-hidden />
          </span>
          <div>
            <h2 className="er-h1 leading-tight">{recording.name}</h2>
            <p className="er-caption text-muted-foreground mt-1 flex items-center gap-2">
              <StatusDot status={recording.status === "compiled" ? "published" : "testing"} />
              {recording.steps.length} steps · {recording.totalDurationMs}ms captured
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          {recording.compiledActionId ? (
            <Button onClick={() => openAction(recording.compiledActionId!)}>
              <Icon name="actions" size={14} aria-hidden /> View compiled action
            </Button>
          ) : (
            <Button onClick={handleCompile} disabled={compileMut.loading}>
              <Icon name="code" size={14} aria-hidden />
              {compileMut.loading ? "Compiling…" : "Compile to action"}
            </Button>
          )}
        </div>
      </div>

      {/* Signal summary */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5 mb-6">
        <SignalTile icon="tasklist" label="Steps" value={recording.steps.length} />
        <SignalTile icon="server" label="Network" value={recording.networkRequests} />
        <SignalTile icon="code" label="DOM mut." value={recording.domMutations} />
        <SignalTile icon="deviceCamera" label="Screenshots" value={recording.screenshots} />
        <SignalTile icon="download" label="HAR" value={recording.harCaptured ? "yes" : "no"} />
      </div>

      {/* Captured steps */}
      <SectionTitle
        icon="workflow"
        title="Captured steps"
        subtitle="The recorded workflow — what Earendel will compile into a typed action"
      />
      <Card className="overflow-hidden p-0">
        <ol className="divide-y divide-border">
          {recording.steps.map((step, i) => {
            const icon = STEP_ICON[step.type] ?? "dot";
            return (
              <li key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-secondary/30">
                <span
                  className="grid size-7 place-items-center rounded-md shrink-0 bg-secondary text-muted-foreground font-mono text-xs font-bold"
                >
                  {step.index + 1}
                </span>
                <Icon name={icon} size={14} className="text-accent mt-1 shrink-0" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-foreground">{step.description}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 er-caption text-muted-foreground">
                    <Badge variant="outline" className="er-pill-neutral text-[10px] capitalize">{step.type}</Badge>
                    {step.selector && (
                      <code className="font-mono text-[11px] text-muted-foreground truncate max-w-xs">
                        {step.selector}
                      </code>
                    )}
                    {step.url && (
                      <code className="font-mono text-[11px] text-muted-foreground truncate max-w-xs">
                        {step.url}
                      </code>
                    )}
                    {step.networkCalls > 0 && (
                      <span className="inline-flex items-center gap-0.5">
                        <Icon name="server" size={9} aria-hidden /> {step.networkCalls}
                      </span>
                    )}
                    <span className="tabular-nums">{step.durationMs}ms</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </Card>

      {/* Connector context */}
      {connector && (
        <div className="mt-6">
          <SectionTitle
            icon="connectors"
            title="Connector"
            subtitle="The authorised bridge this recording was captured against"
          />
          <Card className="gap-3 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className="grid size-9 place-items-center rounded-md bg-primary text-primary-foreground"
              >
                <Icon name="globe" size={16} aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">{connector.name}</p>
                <p className="er-caption text-muted-foreground font-mono">{connector.targetDomain}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => useStudio.getState().openConnector(connector.id)}>
                <Icon name="eye" size={12} aria-hidden /> View connector
              </Button>
            </div>
          </Card>
        </div>
      )}
    </motion.div>
  );
}

function SignalTile({ icon, label, value }: { icon: ErIconName; label: string; value: number | string }) {
  return (
    <Card className="p-3 text-center">
      <Icon name={icon} size={16} className="text-accent mx-auto mb-1" aria-hidden />
      <p className="font-heading text-xl leading-none tabular-nums">{value}</p>
      <p className="er-caption text-muted-foreground mt-0.5">{label}</p>
    </Card>
  );
}

export default RecordingDetailView;
