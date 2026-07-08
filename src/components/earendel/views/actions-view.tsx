"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
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
import { SectionTitle, EmptyState } from "../primitives";
import type {
  ActionStatus,
  RiskLevel,
  TypedAction,
  WorkflowCategory,
} from "@/lib/earendel/types";
import {
  ActionCard,
  CATEGORIES,
  RISKS,
  STATUSES,
} from "./actions-sections";

/**
 * ActionsView — the typed actions catalog.
 *
 * Searchable / filterable grid of compiled TypedActions: signature, risk,
 * permission, execution path (with preferred adapter highlighted), test
 * progress bar, version + published-as chips. Clicking a card opens the
 * action detail view via `useStudio.openAction`.
 */
export function ActionsView() {
  const { data, loading, error, refetch } = useApi<TypedAction[]>(
    () => api.listActions(),
    [],
  );
  const setView = useStudio((s) => s.setView);
  const [search, setSearch] = React.useState("");
  const [category, setCategory] = React.useState<"all" | WorkflowCategory>(
    "all",
  );
  const [status, setStatus] = React.useState<"all" | ActionStatus>("all");
  const [risk, setRisk] = React.useState<"all" | RiskLevel>("all");

  const filtered = React.useMemo(() => {
    const items = data ?? [];
    const q = search.trim().toLowerCase();
    return items.filter((a) => {
      if (category !== "all" && a.category !== category) return false;
      if (status !== "all" && a.status !== status) return false;
      if (risk !== "all" && a.riskLevel !== risk) return false;
      if (
        q &&
        !(
          a.name.toLowerCase().includes(q) ||
          a.signature.toLowerCase().includes(q) ||
          a.description.toLowerCase().includes(q)
        )
      )
        return false;
      return true;
    });
  }, [data, search, category, status, risk]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="actions"
        title="Typed Actions"
        subtitle="Compiled, versioned, risk-gated business verbs your agents can call."
        action={
          <Button onClick={() => setView("recorder")}>
            <Icon name="recorder" size={16} aria-hidden /> New recording
          </Button>
        }
      />

      {/* Filter bar */}
      <Card className="gap-0 p-3">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Icon
              name="search"
              size={14}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search actions…"
              className="pl-8"
              aria-label="Search actions"
            />
          </div>
          <Select
            value={category}
            onValueChange={(v) => setCategory(v as "all" | WorkflowCategory)}
          >
            <SelectTrigger className="w-full" aria-label="Filter by category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={status}
            onValueChange={(v) => setStatus(v as "all" | ActionStatus)}
          >
            <SelectTrigger className="w-full" aria-label="Filter by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={risk}
            onValueChange={(v) => setRisk(v as "all" | RiskLevel)}
          >
            <SelectTrigger className="w-full" aria-label="Filter by risk">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All risks</SelectItem>
              {RISKS.map((r) => (
                <SelectItem key={r} value={r}>
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </Card>

      {error ? (
        <EmptyState
          icon="actions"
          title="Backend connecting…"
          description="Your typed actions will appear here once the FastAPI service is reachable."
          action={
            <Button variant="outline" size="sm" onClick={refetch}>
              <Icon name="sync" size={14} aria-hidden /> Retry
            </Button>
          }
        />
      ) : loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="gap-3 p-4">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-4 w-full" />
            </Card>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="actions"
          title="No actions match"
          description="Adjust filters or record a new workflow to compile an action."
          action={
            <Button size="sm" onClick={() => setView("recorder")}>
              <Icon name="recorder" size={14} aria-hidden /> Record workflow
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((a) => (
            <ActionCard key={a.id} action={a} />
          ))}
        </div>
      )}
    </motion.div>
  );
}

export default ActionsView;
