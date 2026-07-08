"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { Icon } from "../icon";
import { useStudio } from "@/lib/earendel/store";
import { SectionTitle, EmptyState } from "../primitives";
import { ExecutionsList, ExecutionDetail } from "./executions-sections";

/**
 * ExecutionsView — observable infrastructure for every action run.
 *
 * Lists executions with filters (status / caller / adapter) and, when an
 * execution is selected, shows the full trace timeline, inputs/outputs,
 * fallback chain and postcondition result.
 */
export function ExecutionsView() {
  const selectedExecutionId = useStudio((s) => s.selectedExecutionId);

  const backToList = () => {
    // Zustand exposes setState on the hook — clear selection without
    // modifying the store module.
    useStudio.setState({ selectedExecutionId: null, view: "executions" });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="executions"
        title="Executions"
        subtitle="Every action run is a transaction: logged, traced, replayable."
        action={
          selectedExecutionId ? (
            <Button variant="ghost" size="sm" onClick={backToList}>
              <Icon name="chevronLeft" size={14} aria-hidden /> Back to list
            </Button>
          ) : undefined
        }
      />

      {selectedExecutionId ? (
        <ExecutionDetail />
      ) : (
        <>
          <ExecutionsList />
          <EmptyState
            icon="graph"
            title="Click any row to inspect"
            description="The trace timeline shows every adapter attempt, the inputs/outputs, and postcondition results."
          />
        </>
      )}
      <Toaster />
    </motion.div>
  );
}

export default ExecutionsView;
