"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import type { TypedAction, Connector } from "@/lib/earendel/types";
import { RiskBadge, AdapterChip } from "../primitives";

/* ------------------------------------------------------------------ */
/* Dependencies tab — connector, credentials, adapters, permissions    */
/* ------------------------------------------------------------------ */

export function DependenciesTab({ action }: { action: TypedAction }) {
  const openConnector = useStudio((s) => s.openConnector);
  const setView = useStudio((s) => s.setView);
  const { data: connector, loading: connLoading, error: connError } = useApi<Connector>(
    () => api.getConnector(action.connectorId),
    [action.connectorId],
  );

  const adapterChain = action.executionMethods;
  const fallbackDepth = adapterChain.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      {/* Connector dependency */}
      <Card className="gap-3 p-5">
        <div className="flex items-center gap-2">
          <Icon name="connectors" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Connector</h4>
        </div>
        {connError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3">
            <p className="er-caption text-destructive flex items-center gap-1.5">
              <Icon name="alertFill" size={11} aria-hidden /> Connector not found
            </p>
            <p className="er-caption text-muted-foreground mt-1">
              The connector{" "}
              <code className="font-mono text-foreground">{action.connectorId}</code>{" "}
              may have been deleted. The action is orphaned.
            </p>
          </div>
        ) : connLoading ? (
          <p className="er-caption text-muted-foreground flex items-center gap-1.5">
            <Icon name="sync" size={12} className="er-pulse" aria-hidden /> Loading connector…
          </p>
        ) : connector ? (
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
            <Badge className="er-pill-neutral capitalize">{connector.authMethod}</Badge>
            <RiskBadge level={connector.riskLevel} />
            <Button size="sm" variant="outline" onClick={() => openConnector(connector.id)}>
              <Icon name="eye" size={12} aria-hidden /> View
            </Button>
          </div>
        ) : (
          <p className="er-caption text-muted-foreground">Loading connector…</p>
        )}
      </Card>

      {/* Credential vault */}
      {connector && (
        <Card className="gap-3 p-5">
          <div className="flex items-center gap-2">
            <Icon name="lock" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Credential vault</h4>
          </div>
          <div className="rounded-md border border-border bg-background/40 p-3">
            <div className="flex items-center justify-between">
              <code className="font-mono text-xs text-muted-foreground">
                {connector.credentialVaultKey}
              </code>
              <Badge className="er-pill-success">
                <Icon name="shieldCheck" size={10} aria-hidden /> sealed
              </Badge>
            </div>
            <p className="er-caption text-muted-foreground mt-2">
              Credentials are fetched at runtime through the vault — never embedded in LLM
              prompts or logs. RBAC scopes this action to{" "}
              <span className="text-foreground font-medium capitalize">
                {action.permissions.replace("_", " ")}
              </span>{" "}
              operations.
            </p>
          </div>
        </Card>
      )}

      {/* Adapter chain */}
      <Card className="gap-3 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="iterations" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Execution adapters</h4>
          </div>
          <span className="er-caption text-muted-foreground">
            fallback depth {fallbackDepth}
          </span>
        </div>
        <div className="flex flex-col gap-2">
          {adapterChain.map((adapter, i) => {
            const isPreferred = adapter === action.preferredAdapter;
            return (
              <div
                key={adapter}
                className={cn(
                  "flex items-center gap-3 rounded-md border px-3 py-2",
                  isPreferred ? "border-accent/40 bg-accent/5" : "border-border bg-secondary/40",
                )}
              >
                <span className="er-caption text-muted-foreground w-6 text-center font-mono">
                  {i + 1}
                </span>
                <AdapterChip adapter={adapter} active={isPreferred} />
                <span className="text-sm text-muted-foreground flex-1">
                  {isPreferred ? "Preferred — tried first" : "Fallback — tried if preferred fails"}
                </span>
                {isPreferred && (
                  <Badge className="er-pill-success text-xs">preferred</Badge>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Permission + risk summary */}
      <Card className="gap-3 p-5">
        <div className="flex items-center gap-2">
          <Icon name="shield" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Permission & risk</h4>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1">
              Permission scope
            </p>
            <p className="text-sm font-medium capitalize text-foreground">
              {action.permissions.replace("_", " ")}
            </p>
            <p className="er-caption text-muted-foreground mt-1">
              {action.permissions === "read_only"
                ? "Auto-run enabled — no human approval needed."
                : action.permissions === "read_write"
                  ? "Auto-run + log — mutations logged."
                  : action.permissions === "submit"
                    ? "Human confirmation required before submit."
                    : "Strict approval — typed confirmation required."}
            </p>
          </div>
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground uppercase tracking-wide mb-1">
              Risk level
            </p>
            <div className="flex items-center gap-2">
              <RiskBadge level={action.riskLevel} />
            </div>
            <p className="er-caption text-muted-foreground mt-1">
              {action.riskLevel === "low"
                ? "Read-only data retrieval — safe to auto-run."
                : action.riskLevel === "medium"
                  ? "May mutate state — logged + monitored."
                  : action.riskLevel === "high"
                    ? "Consequential — human authorisation required."
                    : "Destructive — strict typed confirmation."}
            </p>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
