"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Icon } from "../icon";
import type { TypedAction } from "@/lib/earendel/types";
import { RiskBadge, CodeBlock } from "../primitives";
import { tsSignature, FieldList, Checklist } from "./action-detail-helpers";

/* ------------------------------------------------------------------ */
/* Contract tab                                                       */
/* ------------------------------------------------------------------ */

export function ContractTab({ action }: { action: TypedAction }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <CodeBlock code={tsSignature(action)} language="typescript" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FieldList title="Inputs" fields={action.contract.inputs} />
        <FieldList title="Outputs" fields={action.contract.outputs} />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Checklist
          title="Preconditions"
          items={action.contract.preconditions}
          icon="shieldCheck"
        />
        <Checklist
          title="Postconditions"
          items={action.contract.postconditions}
          icon="tasklist"
        />
      </div>
      <Card className="gap-2 p-4">
        <div className="flex items-center gap-2">
          <Icon name="lock" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Permission & risk</h4>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="secondary" className="gap-1">
            <Icon name="key" size={12} aria-hidden /> {action.permissions}
          </Badge>
          <RiskBadge level={action.riskLevel} />
          <span className="er-caption text-muted-foreground">
            Read-only flows run automatically; destructive flows require human
            authorisation before each run.
          </span>
        </div>
      </Card>
    </motion.div>
  );
}
