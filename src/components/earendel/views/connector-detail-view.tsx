"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import { useStudio } from "@/lib/earendel/store";
import {
  SectionTitle,
  EmptyState,
  RiskBadge,
  StatusDot,
  AdapterChip,
  CodeBlock,
} from "../primitives";
import type { Connector, TypedAction, Execution, RepairProposal, WorkflowCategory } from "@/lib/earendel/types";

const categoryIcon: Record<WorkflowCategory, "briefcase" | "package" | "law" | "graph" | "person" | "shield" | "law" | "package"> = {
  finance: "briefcase",
  logistics: "package",
  healthcare: "law",
  ecommerce: "graph",
  hr: "person",
  compliance: "shield",
  government: "law",
  other: "package",
};

function MetaRow({ label, value, icon }: { label: string; value: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="er-caption text-muted-foreground inline-flex items-center gap-1.5">
        {icon}
        {label}
      </span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  );
}

/**
 * ConnectorDetailView — drill-down from the connectors list.
 *
 * Shows the connector's identity, vault + permissions, allowed domains, the
 * typed actions compiled against it, and its most recent executions.
 */
export function ConnectorDetailView() {
  const id = useStudio((s) => s.selectedConnectorId);
  const setView = useStudio((s) => s.setView);
  const openAction = useStudio((s) => s.openAction);
  const openExecution = useStudio((s) => s.openExecution);

  const { data: connector, loading, error } = useApi<Connector>(
    () => (id ? api.getConnector(id) : Promise.reject(new Error("no id"))),
    [id],
  );

  const { data: actions } = useApi<TypedAction[]>(
    () => api.listActions(id ?? ""),
    [id],
  );

  const { data: executions } = useApi<Execution[]>(() => api.listExecutions());

  const { data: allRepairs } = useApi<RepairProposal[]>(() => api.listRepairs());

  if (!id) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6 md:p-8">
        <EmptyState
          icon="connectors"
          title="No connector selected"
          description="Pick a connector from the catalog to inspect its bridge details."
          action={
            <Button variant="outline" size="sm" onClick={() => setView("connectors")}>
              <Icon name="arrowRight" size={14} aria-hidden /> Browse connectors
            </Button>
          }
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

  if (error || !connector) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6 md:p-8">
        <EmptyState icon="alert" title="Connector not found" description={error?.message} />
      </div>
    );
  }

  const catIcon = categoryIcon[connector.category];
  const connectorActions = actions ?? [];
  const actionIds = new Set(connectorActions.map((a) => a.id));
  const connectorExecutions = (executions ?? [])
    .filter((e) => actionIds.has(e.actionId))
    .slice(0, 8);
  const connectorRepairs = (allRepairs ?? [])
    .filter((r) => actionIds.has(r.actionId))
    .slice(0, 5);

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
            onClick={() => setView("connectors")}
            aria-label="Back to connectors"
          >
            <Icon name="chevronLeft" size={18} aria-hidden />
          </Button>
          <span
            className="grid size-12 place-items-center rounded-md"
            style={{
              background:
                "linear-gradient(135deg, rgba(107,88,118,0.40), rgba(122,133,72,0.18))",
              color: "#E8E0D4",
              boxShadow: "inset 0 0 0 1px rgba(232,224,212,0.08)",
            }}
          >
            <Icon name={catIcon} size={24} aria-hidden />
          </span>
          <div>
            <h2 className="er-h1 leading-tight">{connector.name}</h2>
            <p className="er-caption text-muted-foreground flex items-center gap-1.5 mt-1">
              <Icon name="globe" size={12} aria-hidden />
              {connector.targetDomain}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusDot status={connector.status} />
          <div className="flex gap-2">
            <RiskBadge level={connector.riskLevel} />
            <Badge variant="outline" className="er-pill-neutral capitalize">
              {connector.permission.replace("_", " ")}
            </Badge>
          </div>
        </div>
      </div>

      <div className="grid gap-5 md:grid-cols-3">
        {/* Identity & vault */}
        <Card className="er-card-raised p-5 md:col-span-2">
          <h3 className="er-h3 mb-3 flex items-center gap-2">
            <Icon name="server" size={18} aria-hidden /> Bridge identity
          </h3>
          <Separator className="mb-2" />
          <MetaRow
            label="Target app"
            value={connector.targetApp}
            icon={<Icon name="browser" size={12} aria-hidden />}
          />
          <MetaRow
            label="Workflow"
            value={connector.workflow}
            icon={<Icon name="workflow" size={12} aria-hidden />}
          />
          <MetaRow
            label="Category"
            value={<span className="capitalize">{connector.category}</span>}
            icon={<Icon name="graph" size={12} aria-hidden />}
          />
          <MetaRow
            label="Auth method"
            value={<span className="capitalize">{connector.authMethod}</span>}
            icon={<Icon name="key" size={12} aria-hidden />}
          />
          <MetaRow
            label="Created"
            value={new Date(connector.createdAt).toLocaleDateString()}
            icon={<Icon name="calendar" size={12} aria-hidden />}
          />

          <h3 className="er-h3 mt-5 mb-3 flex items-center gap-2">
            <Icon name="lock" size={18} aria-hidden /> Credential vault
          </h3>
          <Separator className="mb-2" />
          <div className="rounded-md border border-border bg-background/40 p-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-muted-foreground">
                {connector.credentialVaultKey}
              </span>
              <Badge className="er-pill-success">
                <Icon name="shieldCheck" size={12} aria-hidden /> Sealed
              </Badge>
            </div>
            <p className="er-caption mt-2 text-muted-foreground">
              Credentials are fetched at runtime through the vault — never embedded in
              LLM prompts or logs. RBAC scopes this connector to read-only operations.
            </p>
          </div>

          <h3 className="er-h3 mt-5 mb-3 flex items-center gap-2">
            <Icon name="globe" size={18} aria-hidden /> Allowed domains
          </h3>
          <div className="flex flex-wrap gap-2">
            {connector.allowedDomains.map((d) => (
              <Badge key={d} variant="outline" className="er-pill-neutral font-mono text-xs">
                {d}
              </Badge>
            ))}
            {connector.allowedDomains.length === 0 && (
              <span className="er-caption text-muted-foreground">No domain restrictions recorded.</span>
            )}
          </div>
        </Card>

        {/* Quick actions */}
        <Card className="er-card-raised p-5">
          <h3 className="er-h3 mb-3 flex items-center gap-2">
            <Icon name="tools" size={18} aria-hidden /> Actions
          </h3>
          <Separator className="mb-3" />
          <div className="flex flex-col gap-2">
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => setView("recorder")}
            >
              <Icon name="recorder" size={16} aria-hidden /> Record a new workflow
            </Button>
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => setView("actions")}
            >
              <Icon name="actions" size={16} aria-hidden /> Browse compiled actions
            </Button>
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => setView("executions")}
            >
              <Icon name="executions" size={16} aria-hidden /> View executions
            </Button>
          </div>
          <div className="mt-4 rounded-md border border-dashed border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground">
              <Icon name="lightbulb" size={12} aria-hidden className="inline mr-1" />
              Connectors are the authorised bridge between Earendel and a target app.
              All actions compiled against this connector inherit its risk level and
              permission scope.
            </p>
          </div>
        </Card>
      </div>

      {/* Compiled actions */}
      <div className="mt-8">
        <SectionTitle
          icon="actions"
          title="Compiled actions"
          subtitle={`${connectorActions.length} typed action(s) built on this connector`}
        />
        {connectorActions.length === 0 ? (
          <EmptyState
            icon="actions"
            spot="actions"
            title="No actions compiled yet"
            description="Record a workflow against this connector to compile your first typed action."
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {connectorActions.map((a) => (
              <Card
                key={a.id}
                className="er-card-raised er-lift cursor-pointer p-4"
                onClick={() => openAction(a.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-mono text-sm text-foreground truncate">
                      {a.signature}
                    </p>
                    <p className="er-caption text-muted-foreground mt-1 line-clamp-2">
                      {a.description}
                    </p>
                  </div>
                  <StatusDot status={a.status} />
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <AdapterChip adapter={a.preferredAdapter} active />
                  <Badge variant="outline" className="er-pill-neutral text-xs">
                    v{a.version}
                  </Badge>
                  <span className="er-caption text-muted-foreground ml-auto">
                    {a.testsPassed}/{a.testsTotal} tests
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-2 border-t border-border pt-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation();
                      openAction(a.id);
                    }}
                  >
                    <Icon name="eye" size={12} aria-hidden /> Open
                  </Button>
                  <Button
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      useStudio.setState({ selectedActionId: a.id, view: "playground" });
                    }}
                  >
                    <Icon name="executions" size={12} aria-hidden /> Run
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Recent executions */}
      <div className="mt-8">
        <SectionTitle
          icon="executions"
          title="Recent executions"
          subtitle="Latest runs across actions on this connector"
        />
        {connectorExecutions.length === 0 ? (
          <EmptyState
            icon="executions"
            spot="executions"
            title="No executions yet"
            description="Run an action on this connector to see traces here."
          />
        ) : (
          <Card className="er-card-raised overflow-hidden p-0">
            <div className="divide-y divide-border">
              {connectorExecutions.map((e) => (
                <button
                  key={e.id}
                  onClick={() => openExecution(e.id)}
                  className="er-lift flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-secondary/40"
                >
                  <StatusDot status={e.status} />
                  <span className="font-mono text-sm text-foreground flex-1 truncate">
                    {e.actionName}
                  </span>
                  <AdapterChip adapter={e.adapter} />
                  <span className="er-caption text-muted-foreground w-20 text-right">
                    {e.durationMs}ms
                  </span>
                  <Icon name="chevronRight" size={14} className="text-muted-foreground" aria-hidden />
                </button>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Recent repairs */}
      <div className="mt-8">
        <SectionTitle
          icon="monitoring"
          title="Recent repairs"
          subtitle="Selector-drift proposals for this connector's actions"
        />
        {connectorRepairs.length === 0 ? (
          <EmptyState
            icon="monitoring"
            spot="monitoring"
            title="No repairs needed"
            description="When a canary detects selector drift on this connector's actions, the repair proposals will appear here."
          />
        ) : (
          <div className="flex flex-col gap-3">
            {connectorRepairs.map((r) => (
              <Card key={r.id} className="er-card-raised gap-2 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Icon name="bug" size={12} className="text-chart-4" aria-hidden />
                  <code className="font-mono text-xs text-muted-foreground">
                    v{r.actionVersion}
                  </code>
                  <Badge
                    className={
                      r.status === "pending"
                        ? "er-pill-warn"
                        : r.status === "approved" || r.status === "auto_applied"
                          ? "er-pill-success"
                          : "er-pill-danger"
                    }
                  >
                    {r.status.replace("_", " ")}
                  </Badge>
                  <span className="ml-auto font-heading text-lg tabular-nums">
                    {Math.round(r.confidence * 100)}%
                  </span>
                </div>
                <p className="er-caption text-muted-foreground line-clamp-2">{r.reason}</p>
                <div className="flex items-center gap-2 mt-1">
                  <code className="font-mono text-[11px] text-destructive/80 line-through truncate">
                    {r.failedSelector}
                  </code>
                  <Icon name="arrowRight" size={10} className="text-muted-foreground shrink-0" aria-hidden />
                  <code className="font-mono text-[11px] text-accent truncate">
                    {r.candidateSelector}
                  </code>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default ConnectorDetailView;
