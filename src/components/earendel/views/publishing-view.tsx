"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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
import type { TypedAction } from "@/lib/earendel/types";
import { SectionTitle, EmptyState } from "../primitives";
import {
  McpTab,
  RestTab,
  SdkTab,
  WebhookTab,
  type RichPublishedTool,
} from "./publishing-sections";
import { RegistryTab } from "./publishing-registry";

/* ------------------------------------------------------------------ */
/* PublishingView                                                     */
/* ------------------------------------------------------------------ */

export function PublishingView() {
  const { data: actions, loading: actionsLoading } = useApi<TypedAction[]>(
    () => api.listActions(),
    [],
  );
  const published = (actions ?? []).filter((a) => a.publishedAs.length > 0);
  const firstId = published[0]?.id ?? actions?.[0]?.id ?? null;
  const [selectedId, setSelectedId] = React.useState<string | null>(firstId);

  React.useEffect(() => {
    if (!selectedId && firstId) setSelectedId(firstId);
  }, [firstId, selectedId]);

  const { data: tool, loading, error } = useApi<RichPublishedTool>(
    () =>
      selectedId
        ? api.getPublishedTool(selectedId)
        : Promise.reject(new Error("no-id")),
    [selectedId],
    { enabled: !!selectedId },
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="publishing"
        title="Publishing"
        subtitle="One compiled action, every consumer surface: MCP, REST, SDK, webhook."
      />

      <Card className="gap-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Icon name="actions" size={14} aria-hidden />
            <span className="text-sm font-medium">Action</span>
          </div>
          <Select
            value={selectedId ?? undefined}
            onValueChange={(v) => setSelectedId(v)}
            disabled={actionsLoading || (actions?.length ?? 0) === 0}
          >
            <SelectTrigger className="w-72" aria-label="Select published action">
              <SelectValue placeholder="Select an action" />
            </SelectTrigger>
            <SelectContent>
              {(actions ?? []).map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.name} · v{a.version}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {tool && (
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="er-caption">
              v{tool.version ?? "—"}
            </Badge>
            {(tool.publishedAs ?? []).map((p) => (
              <Badge key={p} variant="secondary" className="er-caption">
                {p}
              </Badge>
            ))}
          </div>
        )}
      </Card>

      <Tabs defaultValue="registry" className="gap-4">
        <TabsList className="flex h-auto flex-wrap">
          <TabsTrigger value="registry">
            <Icon name="server" size={14} aria-hidden /> Registry
          </TabsTrigger>
          <TabsTrigger value="mcp" disabled={!tool}>
            <Icon name="robot" size={14} aria-hidden /> MCP Tool
          </TabsTrigger>
          <TabsTrigger value="rest" disabled={!tool}>
            <Icon name="server" size={14} aria-hidden /> REST API
          </TabsTrigger>
          <TabsTrigger value="sdk" disabled={!tool}>
            <Icon name="code" size={14} aria-hidden /> SDK
          </TabsTrigger>
          <TabsTrigger value="webhook" disabled={!tool}>
            <Icon name="link" size={14} aria-hidden /> Webhook
          </TabsTrigger>
        </TabsList>
        <TabsContent value="registry">
          <RegistryTab />
        </TabsContent>
        <TabsContent value="mcp">
          {!selectedId ? (
            <EmptyState
              icon="publishing"
              title="No action selected"
              description="Pick a published action above to inspect its MCP tool definition."
            />
          ) : error ? (
            <EmptyState
              icon="alert"
              title="Backend connecting…"
              description="Published tool definitions will appear here shortly."
            />
          ) : loading || !tool ? (
            <Skeleton className="h-96 w-full" />
          ) : (
            <McpTab tool={tool} />
          )}
        </TabsContent>
        <TabsContent value="rest">
          {!tool ? (
            <EmptyState icon="publishing" title="No action selected" />
          ) : (
            <RestTab tool={tool} />
          )}
        </TabsContent>
        <TabsContent value="sdk">
          {!tool ? (
            <EmptyState icon="publishing" title="No action selected" />
          ) : (
            <SdkTab tool={tool} />
          )}
        </TabsContent>
        <TabsContent value="webhook">
          {!tool ? (
            <EmptyState icon="publishing" title="No action selected" />
          ) : (
            <WebhookTab tool={tool} />
          )}
        </TabsContent>
      </Tabs>

    </motion.div>
  );
}

export default PublishingView;
