"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Icon, type ErIconName } from "../icon";
import { useApiMutation } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import { useStudio } from "@/lib/earendel/store";
import { toast } from "@/hooks/use-toast";
import { RiskBadge, StatusDot } from "../primitives";
import type {
  Connector,
  PermissionScope,
  RiskLevel,
  WorkflowCategory,
} from "@/lib/earendel/types";

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

export const CATEGORY_ICON: Record<WorkflowCategory, ErIconName> = {
  finance: "briefcase",
  logistics: "package",
  healthcare: "law",
  ecommerce: "cloud",
  hr: "person",
  compliance: "shieldCheck",
  government: "briefcase",
  other: "gear",
};

const PERMISSION_VARIANT: Record<PermissionScope, string> = {
  read_only: "bg-secondary text-foreground",
  read_write: "bg-chart-4/25 text-foreground",
  submit: "bg-primary/30 text-foreground",
  destructive: "bg-destructive/30 text-foreground",
};

export function PermissionBadge({ scope }: { scope: PermissionScope }) {
  return (
    <Badge
      variant="outline"
      className={cn("border-transparent", PERMISSION_VARIANT[scope])}
    >
      <Icon name="key" size={12} aria-hidden /> {scope.replace("_", " ")}
    </Badge>
  );
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

/* ------------------------------------------------------------------ */
/* ConnectorCard                                                       */
/* ------------------------------------------------------------------ */

export function ConnectorCard({ connector }: { connector: Connector }) {
  const [open, setOpen] = React.useState(false);
  const setView = useStudio((s) => s.setView);
  const openConnector = useStudio((s) => s.openConnector);
  const catIcon = CATEGORY_ICON[connector.category] ?? "gear";

  return (
    <Card
      className="gap-3 p-4 cursor-pointer"
      onClick={() => openConnector(connector.id)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground"
            >
              <Icon name={catIcon} size={14} aria-hidden />
            </span>
            <p className="truncate font-heading text-lg leading-tight">
              {connector.name}
            </p>
          </div>
          <p className="er-caption mt-1 flex items-center gap-1 text-muted-foreground">
            <Icon name="globe" size={12} aria-hidden /> {connector.targetDomain}
          </p>
        </div>
        <StatusDot status={connector.status} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <PermissionBadge scope={connector.permission} />
        <RiskBadge level={connector.riskLevel} />
      </div>

      <div className="flex flex-wrap gap-1">
        {connector.allowedDomains.map((d) => (
          <span
            key={d}
            className="inline-flex items-center gap-1 rounded border border-border bg-secondary px-1.5 py-0.5 font-mono er-caption text-muted-foreground"
          >
            <Icon name="link" size={10} aria-hidden /> {d}
          </span>
        ))}
      </div>

      <div className="flex items-center justify-between border-t border-border pt-2 er-caption text-muted-foreground">
        <span className="inline-flex items-center gap-1 font-mono">
          <Icon name="lock" size={12} aria-hidden /> {connector.credentialVaultKey}
          /••••
        </span>
        <span className="inline-flex items-center gap-1">
          <Icon name="calendar" size={12} aria-hidden />{" "}
          {formatDate(connector.createdAt)}
        </span>
      </div>

      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="w-full justify-between">
            <span className="inline-flex items-center gap-1.5">
              <Icon
                name={open ? "chevronDown" : "chevronRight"}
                size={14}
                aria-hidden
              />
              {open ? "Hide details" : "Show workflow details"}
            </span>
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2 space-y-3">
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="er-caption text-muted-foreground uppercase tracking-wide">
              Workflow
            </p>
            <p className="mt-1 font-mono text-sm">{connector.workflow}</p>
          </div>
          <div className="flex items-center justify-between gap-2 er-caption text-muted-foreground">
            <span>
              Auth:{" "}
              <span className="font-mono text-foreground">
                {connector.authMethod}
              </span>
            </span>
            <span>
              Category: <span className="text-foreground">{connector.category}</span>
            </span>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="rounded-full"
              onClick={() => openConnector(connector.id)}
            >
              <Icon name="eye" size={14} aria-hidden /> View
            </Button>
            <Button size="sm" className="rounded-full" onClick={() => setView("recorder")}>
              <Icon name="recorder" size={14} aria-hidden /> Record workflow
            </Button>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* NewConnectorDialog                                                  */
/* ------------------------------------------------------------------ */

const CATEGORIES: WorkflowCategory[] = [
  "finance",
  "healthcare",
  "logistics",
  "ecommerce",
  "hr",
  "compliance",
  "government",
  "other",
];
const PERMISSIONS: PermissionScope[] = [
  "read_only",
  "read_write",
  "submit",
  "destructive",
];
const RISKS: RiskLevel[] = ["low", "medium", "high", "critical"];
const AUTH_METHODS: Connector["authMethod"][] = [
  "password",
  "sso",
  "api_key",
  "oauth",
];

interface NewConnectorForm {
  name: string;
  targetApp: string;
  targetDomain: string;
  workflow: string;
  category: WorkflowCategory;
  permission: PermissionScope;
  riskLevel: RiskLevel;
  authMethod: Connector["authMethod"];
  allowedDomains: string;
}

const INITIAL_FORM: NewConnectorForm = {
  name: "",
  targetApp: "",
  targetDomain: "",
  workflow: "",
  category: "finance",
  permission: "read_only",
  riskLevel: "low",
  authMethod: "password",
  allowedDomains: "",
};

export function NewConnectorDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = React.useState(false);
  const [form, setForm] = React.useState<NewConnectorForm>(INITIAL_FORM);
  const { mutate, loading } = useApiMutation<Partial<Connector>, Connector>(
    (body) => api.createConnector(body),
  );

  const update = <K extends keyof NewConnectorForm>(
    key: K,
    val: NewConnectorForm[K],
  ) => setForm((f) => ({ ...f, [key]: val }));

  const reset = () => setForm(INITIAL_FORM);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.targetDomain.trim()) {
      toast({
        title: "Missing fields",
        description: "Name and target domain are required.",
        variant: "destructive",
      });
      return;
    }
    const allowed = form.allowedDomains
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const payload: Partial<Connector> = {
      name: form.name.trim(),
      targetApp: form.targetApp.trim() || form.name.trim(),
      targetDomain: form.targetDomain.trim(),
      workflow: form.workflow.trim() || form.name.trim(),
      category: form.category,
      permission: form.permission,
      riskLevel: form.riskLevel,
      authMethod: form.authMethod,
      allowedDomains:
        allowed.length > 0 ? allowed : [form.targetDomain.trim()],
    };
    try {
      await mutate(payload);
      toast({
        title: "Connector created",
        description: `${payload.name} is now authorized.`,
      });
      setOpen(false);
      reset();
      onCreated();
    } catch {
      toast({
        title: "Could not create connector",
        description: "Backend unreachable or invalid payload.",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button className="rounded-full">
          <Icon name="plus" size={16} aria-hidden /> New connector
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl">
            Create connector
          </DialogTitle>
          <DialogDescription>
            Authorize Earendel to bridge a portal or app your team already
            uses.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={onSubmit}
          className="grid grid-cols-1 gap-4 sm:grid-cols-2"
        >
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="cn-name">Connector name</Label>
            <Input
              id="cn-name"
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
              placeholder="Acme Supplier Portal"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cn-app">Target app</Label>
            <Input
              id="cn-app"
              value={form.targetApp}
              onChange={(e) => update("targetApp", e.target.value)}
              placeholder="Acme Supplier Portal"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cn-domain">Target domain</Label>
            <Input
              id="cn-domain"
              value={form.targetDomain}
              onChange={(e) => update("targetDomain", e.target.value)}
              placeholder="supplier-portal.acme.com"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cn-workflow">Workflow</Label>
            <Input
              id="cn-workflow"
              value={form.workflow}
              onChange={(e) => update("workflow", e.target.value)}
              placeholder="downloadInvoice"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cn-domains">
              Allowed domains (comma-separated)
            </Label>
            <Input
              id="cn-domains"
              value={form.allowedDomains}
              onChange={(e) => update("allowedDomains", e.target.value)}
              placeholder="supplier-portal.acme.com, cdn.acme.com"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Category</Label>
            <Select
              value={form.category}
              onValueChange={(v) => update("category", v as WorkflowCategory)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Permission</Label>
            <Select
              value={form.permission}
              onValueChange={(v) => update("permission", v as PermissionScope)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERMISSIONS.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p.replace("_", " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Risk level</Label>
            <Select
              value={form.riskLevel}
              onValueChange={(v) => update("riskLevel", v as RiskLevel)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RISKS.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Auth method</Label>
            <Select
              value={form.authMethod}
              onValueChange={(v) =>
                update("authMethod", v as Connector["authMethod"])
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AUTH_METHODS.map((a) => (
                  <SelectItem key={a} value={a}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter className="sm:col-span-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" className="rounded-full" disabled={loading}>
              <Icon name={loading ? "sync" : "plus"} size={14} aria-hidden />
              {loading ? "Creating…" : "Create connector"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
