"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Icon, type ErIconName } from "../icon";
import { useApi } from "../use-api";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import type { TypedAction } from "@/lib/earendel/types";
import { StatusDot, RiskBadge, EmptyState } from "../primitives";
import {
  ContractTab,
  ExecutionTab,
  TestsCanaryTab,
  VersionsTab,
  ExecutionsTab,
} from "./action-detail-sections";

type PublishTarget = "mcp" | "rest" | "sdk" | "webhook";

const TARGETS: { id: PublishTarget; label: string; icon: ErIconName; hint: string }[] = [
  { id: "mcp", label: "MCP tool", icon: "robot", hint: "Callable by Claude / Cursor / Cline" },
  { id: "rest", label: "REST API", icon: "server", hint: "POST endpoint with typed schema" },
  { id: "sdk", label: "SDK function", icon: "code", hint: "TypeScript + Python packages" },
  { id: "webhook", label: "Webhook", icon: "link", hint: "Triggerable from n8n / Zapier / Make" },
];

const CATEGORY_ICON: Record<TypedAction["category"], ErIconName> = {
  finance: "briefcase",
  healthcare: "heart",
  logistics: "package",
  ecommerce: "package",
  hr: "person",
  compliance: "law",
  government: "shield",
  other: "tools",
};

function PublishDialog({
  open,
  onOpenChange,
  action,
  onDone,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  action: TypedAction;
  onDone: () => void;
}) {
  const [targets, setTargets] = React.useState<Set<PublishTarget>>(
    () => new Set(action.publishedAs as PublishTarget[]),
  );
  const [publishing, setPublishing] = React.useState(false);

  const toggle = (t: PublishTarget) => {
    setTargets((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const confirm = async () => {
    if (targets.size === 0) {
      toast.error("Pick at least one target");
      return;
    }
    setPublishing(true);
    try {
      await api.publishAction(action.id, Array.from(targets));
      toast.success("Action published", {
        description: `${action.name} live on ${Array.from(targets).join(", ")}.`,
      });
      onDone();
      onOpenChange(false);
    } catch {
      toast.error("Publish failed", { description: "Backend unreachable." });
    } finally {
      setPublishing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl">
            Publish {action.name}
          </DialogTitle>
          <DialogDescription>
            Choose the surfaces this action should be callable from. Earendel
            compiles a fresh contract for each.
          </DialogDescription>
        </DialogHeader>
        <ul className="grid gap-2">
          {TARGETS.map((t) => {
            const checked = targets.has(t.id);
            return (
              <li key={t.id}>
                <label
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-md border border-border p-3 transition-colors",
                    checked ? "bg-accent/10" : "hover:bg-secondary/50",
                  )}
                >
                  <Checkbox checked={checked} onCheckedChange={() => toggle(t.id)} />
                  <span className="grid size-7 place-items-center rounded-md bg-secondary">
                    <Icon name={t.icon} size={14} aria-hidden />
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-medium">{t.label}</span>
                    <span className="block er-caption text-muted-foreground">
                      {t.hint}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={publishing}>
            Cancel
          </Button>
          <Button onClick={confirm} disabled={publishing}>
            <Icon name="publishing" size={14} aria-hidden />
            {publishing ? "Publishing…" : "Approve and publish"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Header({ action, refetch }: { action: TypedAction; refetch: () => void }) {
  const setView = useStudio((s) => s.setView);
  const [publishOpen, setPublishOpen] = React.useState(false);

  return (
    <Card className="er-surface gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to actions"
            onClick={() => setView("actions")}
          >
            <Icon name="chevronLeft" size={18} aria-hidden />
          </Button>
          <span className="grid size-10 place-items-center rounded-md bg-primary/20 text-primary">
            <Icon name={CATEGORY_ICON[action.category]} size={20} aria-hidden />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <code className="font-mono text-2xl text-foreground">{action.signature}</code>
              <Badge variant="outline" className="er-caption">
                v{action.version}
              </Badge>
            </div>
            <p className="er-body mt-1 text-muted-foreground">{action.description}</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <StatusDot status={action.status} />
              <RiskBadge level={action.riskLevel} />
              <Badge variant="secondary" className="gap-1">
                <Icon name="key" size={11} aria-hidden /> {action.permissions}
              </Badge>
              {action.publishedAs.map((p) => (
                <Badge key={p} variant="outline" className="er-caption">
                  {p}
                </Badge>
              ))}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setView("playground")}>
            <Icon name="playground" size={14} aria-hidden /> Run
          </Button>
          <Button onClick={() => setPublishOpen(true)}>
            <Icon name="publishing" size={14} aria-hidden /> Publish
          </Button>
        </div>
      </div>
      <PublishDialog
        open={publishOpen}
        onOpenChange={setPublishOpen}
        action={action}
        onDone={refetch}
      />
    </Card>
  );
}

export function ActionDetailView() {
  const actionId = useStudio((s) => s.selectedActionId);
  const { data, loading, error, refetch } = useApi<TypedAction>(
    () => (actionId ? api.getAction(actionId) : Promise.reject(new Error("no-id"))),
    [actionId],
    { enabled: !!actionId },
  );

  if (!actionId) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="mx-auto w-full max-w-6xl p-6 md:p-8"
      >
        <EmptyState
          icon="actions"
          title="No action selected"
          description="Pick an action from the catalog to inspect its contract."
        />
  
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-6 md:p-8"
    >
      {error ? (
        <EmptyState
          icon="alert"
          title="Backend connecting…"
          description="The action contract will appear here once the FastAPI service is reachable."
        />
      ) : loading || !data ? (
        <div className="space-y-4">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          <Header action={data} refetch={refetch} />
          <Tabs defaultValue="contract" className="gap-4">
            <TabsList className="flex h-auto flex-wrap">
              <TabsTrigger value="contract">
                <Icon name="code" size={14} aria-hidden /> Contract
              </TabsTrigger>
              <TabsTrigger value="execution">
                <Icon name="workflow" size={14} aria-hidden /> Execution
              </TabsTrigger>
              <TabsTrigger value="tests">
                <Icon name="beaker" size={14} aria-hidden /> Tests &amp; Canary
              </TabsTrigger>
              <TabsTrigger value="versions">
                <Icon name="versions" size={14} aria-hidden /> Versions
              </TabsTrigger>
              <TabsTrigger value="executions">
                <Icon name="executions" size={14} aria-hidden /> Executions
              </TabsTrigger>
            </TabsList>
            <TabsContent value="contract">
              <ContractTab action={data} />
            </TabsContent>
            <TabsContent value="execution">
              <ExecutionTab action={data} />
            </TabsContent>
            <TabsContent value="tests">
              <TestsCanaryTab action={data} />
            </TabsContent>
            <TabsContent value="versions">
              <VersionsTab action={data} />
            </TabsContent>
            <TabsContent value="executions">
              <ExecutionsTab actionId={data.id} />
            </TabsContent>
          </Tabs>
        </>
      )}

    </motion.div>
  );
}

export default ActionDetailView;
