"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import { useStudio } from "@/lib/earendel/store";
import { toast } from "@/hooks/use-toast";
import { SectionTitle } from "../primitives";
import type {
  CapturedStep,
  Connector,
  Recording,
  TypedAction,
} from "@/lib/earendel/types";
import {
  buildSimulation, CapturedStepsPanel, CaptureExplainer, FauxBrowser,
} from "./recorder-sections";

/**
 * RecorderView — the "Record workflow once" step.
 *
 * A faux secure browser session + a client-side simulation that progressively
 * reveals ~7 captured steps. After all steps are captured, "Stop & compile"
 * POSTs the recording and compiles it to a typed action. The simulation is a
 * demo — the backend recording simulator generates its own steps.
 */
export function RecorderView() {
  const { data: connectors } = useApi<Connector[]>(
    () => api.listConnectors(),
    [],
  );
  const selectedConnectorId = useStudio((s) => s.selectedConnectorId);
  const openAction = useStudio((s) => s.openAction);

  const [connectorId, setConnectorId] = React.useState<string>(
    selectedConnectorId ?? "",
  );
  const [workflowName, setWorkflowName] = React.useState("downloadInvoice");
  const [recording, setRecording] = React.useState(false);
  const [revealed, setRevealed] = React.useState<CapturedStep[]>([]);
  const [compileLoading, setCompileLoading] = React.useState(false);
  const [compiledActionId, setCompiledActionId] = React.useState<string | null>(
    null,
  );
  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const indexRef = React.useRef(0);

  const selected = (connectors ?? []).find((c) => c.id === connectorId);
  const simulation = React.useMemo(() => buildSimulation(selected), [selected]);

  React.useEffect(() => {
    if (!connectorId && connectors && connectors.length > 0) {
      setConnectorId(selectedConnectorId ?? connectors[0].id);
    }
  }, [connectors, connectorId, selectedConnectorId]);

  React.useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  // Auto-stop when the last seeded step has been revealed.
  React.useEffect(() => {
    if (
      recording &&
      simulation.length > 0 &&
      revealed.length >= simulation.length
    ) {
      if (timerRef.current) clearInterval(timerRef.current);
      setRecording(false);
    }
  }, [recording, revealed.length, simulation.length]);

  const start = () => {
    if (!connectorId) {
      toast({
        title: "Select a connector",
        description: "Pick a target app to record against.",
        variant: "destructive",
      });
      return;
    }
    setRevealed([]);
    setCompiledActionId(null);
    indexRef.current = 0;
    setRecording(true);
    const steps = simulation;
    timerRef.current = setInterval(() => {
      setRevealed((prev) => {
        const next = steps[indexRef.current];
        if (!next) {
          if (timerRef.current) clearInterval(timerRef.current);
          return prev;
        }
        indexRef.current += 1;
        return [...prev, next];
      });
    }, 900);
  };

  const stop = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setRecording(false);
    setRevealed(simulation);
  };

  const compile = async () => {
    setCompileLoading(true);
    try {
      const payload = {
        connectorId,
        name: workflowName || "recordedWorkflow",
        workflowName: workflowName || "recordedWorkflow",
      } as unknown as Partial<Recording>;
      const rec = await api.createRecording(payload);
      // Backend returns the action directly; client types wrap as `{action}`.
      const result = (await api.compileRecording(rec.id)) as unknown;
      const action = (
        (result as { action?: TypedAction }).action ?? result
      ) as TypedAction;
      setCompiledActionId(action.id);
      toast({
        title: "Compiled to typed action",
        description: `${action.signature} is ready.`,
      });
    } catch {
      toast({
        title: "Compile failed",
        description: "Backend unreachable.",
        variant: "destructive",
      });
    } finally {
      setCompileLoading(false);
    }
  };

  const allRevealed = revealed.length === simulation.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="recorder"
        title="Workflow Recorder"
        subtitle="Record a human workflow once. Earendel captures every signal — DOM, network, screenshots — and compiles it into a typed action."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="flex flex-col gap-4">
          <FauxBrowser connector={selected} />

          <Card className="gap-3 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="rec-connector">Connector</Label>
                <Select value={connectorId} onValueChange={setConnectorId}>
                  <SelectTrigger id="rec-connector" className="w-full">
                    <SelectValue placeholder="Select connector" />
                  </SelectTrigger>
                  <SelectContent>
                    {(connectors ?? []).map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rec-name">Workflow name</Label>
                <Input
                  id="rec-name"
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  placeholder="downloadInvoice"
                />
              </div>
            </div>
            <div className="flex gap-2">
              {compiledActionId ? (
                <Button
                  onClick={() => openAction(compiledActionId)}
                  className="flex-1"
                >
                  <Icon name="arrowRight" size={16} aria-hidden /> View action
                </Button>
              ) : allRevealed && !recording ? (
                <Button
                  onClick={compile}
                  disabled={compileLoading}
                  className="flex-1"
                >
                  <Icon
                    name={compileLoading ? "sync" : "workflow"}
                    size={16}
                    aria-hidden
                  />
                  {compileLoading ? "Compiling…" : "Stop & compile"}
                </Button>
              ) : recording ? (
                <Button
                  onClick={stop}
                  variant="destructive"
                  className="er-pulse flex-1"
                >
                  <Icon name="stop" size={16} aria-hidden /> Stop recording
                </Button>
              ) : (
                <Button
                  onClick={start}
                  disabled={!connectorId}
                  className="flex-1"
                >
                  <Icon name="dotFill" size={16} aria-hidden />{" "}
                  {revealed.length > 0 ? "Resume" : "Record"}
                </Button>
              )}
            </div>
          </Card>

          <CapturedStepsPanel revealed={revealed} recording={recording} />
        </div>

        <CaptureExplainer />
      </div>
    </motion.div>
  );
}

export default RecorderView;
