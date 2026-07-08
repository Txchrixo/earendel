"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Icon, type ErIconName } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import type { PublishedTool, TypedAction, McpRegistry } from "@/lib/earendel/types";
import { SectionTitle, CodeBlock, EmptyState, RiskBadge } from "../primitives";

/* ------------------------------------------------------------------ */
/* The backend returns a richer shape than the shared TS type, so we  */
/* narrow locally without modifying types.ts.                         */
/* ------------------------------------------------------------------ */

interface RichPublishedTool extends PublishedTool {
  name?: string;
  version?: string;
  publishedAs?: ("mcp" | "rest" | "sdk" | "webhook")[];
  mcpDefinition: string | Record<string, unknown>;
  contract?: {
    inputs: { name: string; type: string; required: boolean; description?: string }[];
    outputs: { name: string; type: string; required: boolean; description?: string }[];
    preconditions: string[];
    postconditions: string[];
  };
}

function useActionName(tool: RichPublishedTool | undefined): string {
  return tool?.name ?? tool?.actionName ?? "";
}

/* ------------------------------------------------------------------ */
/* MCP tab                                                            */
/* ------------------------------------------------------------------ */

const COMPAT = [
  { name: "Claude", icon: "hubot" as ErIconName },
  { name: "Cursor", icon: "terminal" as ErIconName },
  { name: "Cline", icon: "robot" as ErIconName },
  { name: "Continue", icon: "code" as ErIconName },
];

function McpTab({ tool }: { tool: RichPublishedTool }) {
  const name = useActionName(tool);
  const def =
    typeof tool.mcpDefinition === "string"
      ? tool.mcpDefinition
      : JSON.stringify(tool.mcpDefinition, null, 2);
  const registrySnippet = JSON.stringify(
    {
      mcpServers: {
        earendel: {
          url: `https://api.earendel.io/mcp/${tool.actionId}`,
          transport: "http",
        },
      },
    },
    null,
    2,
  );
  const description =
    (typeof tool.mcpDefinition === "object" &&
      (tool.mcpDefinition as { description?: string }).description) ||
    `Earendel published action: ${name}`;

  const copyRegistry = async () => {
    try {
      await navigator.clipboard.writeText(registrySnippet);
      toast.success("Copied MCP registry snippet");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Icon name="robot" size={14} className="text-accent" aria-hidden />
          <code className="font-mono text-sm">{tool.mcpToolName}</code>
          <Badge variant="outline" className="er-caption">
            mcp 2024-11
          </Badge>
        </div>
        <p className="er-caption text-muted-foreground">{description}</p>
      </Card>

      <Card className="gap-2 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="package" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Tool definition</h4>
          </div>
        </div>
        <CodeBlock code={def} language="json" />
      </Card>

      <Card className="gap-2 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="copy" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Add to your MCP registry</h4>
          </div>
          <Button size="sm" variant="outline" onClick={copyRegistry}>
            <Icon name="copy" size={12} aria-hidden /> Copy snippet
          </Button>
        </div>
        <CodeBlock code={registrySnippet} language="json" />
      </Card>

      <Card className="gap-2 border-accent/30 bg-accent/5 p-4">
        <div className="flex items-center gap-2">
          <Icon name="lightbulb" size={14} className="text-chart-4" aria-hidden />
          <h4 className="text-sm font-medium">How agents consume this</h4>
        </div>
        <p className="er-caption text-muted-foreground">
          MCP standardises how LLM apps expose and consume tools. Your action is
          now callable by any MCP-aware agent — inputs are validated against the
          published JSON schema, every call is logged as an Execution, and
          outputs match the declared contract.
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          {COMPAT.map((c) => (
            <span
              key={c.name}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary px-2 py-1 er-caption"
            >
              <Icon name={c.icon} size={12} aria-hidden />
              {c.name}
              <Icon name="check" size={11} className="text-accent" aria-hidden />
            </span>
          ))}
        </div>
      </Card>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* REST tab                                                           */
/* ------------------------------------------------------------------ */

function RestTab({ tool }: { tool: RichPublishedTool }) {
  const name = useActionName(tool);
  const inputs = tool.contract?.inputs ?? [];
  const outputs = tool.contract?.outputs ?? [];

  const bodySchema = JSON.stringify(
    {
      type: "object",
      properties: Object.fromEntries(
        inputs.map((i) => [i.name, { type: i.type, description: i.description }]),
      ),
      required: inputs.filter((i) => i.required).map((i) => i.name),
    },
    null,
    2,
  );

  const sampleResponse = JSON.stringify(
    Object.fromEntries(outputs.map((o) => [o.name, sampleValue(o.type)])),
    null,
    2,
  );

  const curl = `curl -X POST '${tool.restEndpoint}' \\
  -H 'Authorization: Bearer $EARENDEL_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify(Object.fromEntries(inputs.map((i) => [i.name, sampleValue(i.type)])))}'`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className="bg-accent text-accent-foreground">POST</Badge>
          <code className="font-mono text-sm">{tool.restEndpoint}</code>
        </div>
        <p className="er-caption text-muted-foreground">
          Typed REST endpoint for {name}. Returns 200 with the declared output
          schema or 422 on contract violation.
        </p>
      </Card>
      <Card className="gap-2 p-4">
        <div className="flex items-center gap-2">
          <Icon name="terminal" size={14} aria-hidden />
          <h4 className="text-sm font-medium">curl example</h4>
        </div>
        <CodeBlock code={curl} language="bash" />
      </Card>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="gap-2 p-4">
          <div className="flex items-center gap-2">
            <Icon name="arrowDown" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Request body schema</h4>
          </div>
          <CodeBlock code={bodySchema} language="json" />
        </Card>
        <Card className="gap-2 p-4">
          <div className="flex items-center gap-2">
            <Icon name="arrowRight" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Sample 200 response</h4>
          </div>
          <CodeBlock code={sampleResponse} language="json" />
        </Card>
      </div>
    </motion.div>
  );
}

function sampleValue(type: string): unknown {
  switch (type) {
    case "string":
      return "sample";
    case "number":
      return 1234.56;
    case "boolean":
      return true;
    case "url":
      return "https://files.earendel.io/sample.pdf";
    case "date":
      return "2026-07-08";
    default:
      return null;
  }
}

/* ------------------------------------------------------------------ */
/* SDK tab                                                            */
/* ------------------------------------------------------------------ */

function SdkTab({ tool }: { tool: RichPublishedTool }) {
  const name = useActionName(tool);
  const [lang, setLang] = React.useState<"typescript" | "python">("typescript");
  const inputs = tool.contract?.inputs ?? [];
  const args = inputs.map((i) => `${i.name}: ${tsType(i.type)}`).join(", ");
  const callArgs = inputs.map((i) => `${i.name}: ${sampleValue(i.type) as string}`).join(", ");

  const ts = `import { Earendel } from '@earendel/sdk';

const client = new Earendel({ apiKey: process.env.EARENDEL_API_KEY });

// ${name}(${args})
const result = await client.actions.${name}({
  ${inputs.map((i) => `${i.name}: ${JSON.stringify(sampleValue(i.type))}`).join(",\n  ")}
});

console.log(result);
// → { ${tool.contract?.outputs.map((o) => o.name).join(", ")} }`;

  const py = `from earendel import Earendel

client = Earendel(api_key=os.environ['EARENDEL_API_KEY'])

# ${name}(${args})
result = client.actions.${name}(
    ${inputs.map((i) => `${i.name}=${JSON.stringify(sampleValue(i.type))}`).join(",\n    ")}
)

print(result)
# → { ${tool.contract?.outputs.map((o) => o.name).join(", ")} }`;

  void callArgs;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-2 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon name="code" size={14} aria-hidden />
            <h4 className="text-sm font-medium">SDK function</h4>
          </div>
          <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
            {(["typescript", "python"] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLang(l)}
                className={cn(
                  "rounded px-2 py-0.5 er-caption capitalize",
                  lang === l ? "bg-secondary text-foreground" : "text-muted-foreground",
                )}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        <code className="font-mono text-sm">
          {name}({args})
        </code>
      </Card>
      <CodeBlock
        code={lang === "typescript" ? ts : py}
        language={lang === "typescript" ? "typescript" : "python"}
      />
      <Card className="gap-2 border-accent/30 bg-accent/5 p-4">
        <div className="flex items-center gap-2">
          <Icon name="package" size={14} className="text-chart-4" aria-hidden />
          <h4 className="text-sm font-medium">Install</h4>
        </div>
        <CodeBlock
          code={
            lang === "typescript"
              ? "npm install @earendel/sdk"
              : "pip install earendel-sdk"
          }
          language="bash"
        />
      </Card>
    </motion.div>
  );
}

function tsType(t: string): string {
  if (t === "string") return "string";
  if (t === "number") return "number";
  if (t === "boolean") return "boolean";
  if (t === "url") return "string";
  if (t === "date") return "string";
  if (t === "file") return "Blob";
  return "string";
}

/* ------------------------------------------------------------------ */
/* Webhook tab                                                        */
/* ------------------------------------------------------------------ */

function WebhookTab({ tool }: { tool: RichPublishedTool }) {
  const samplePayload = JSON.stringify(
    {
      event: "action.completed",
      actionId: tool.actionId,
      actionName: useActionName(tool),
      executionId: "exe_sample",
      status: "success",
      outputs: Object.fromEntries(
        (tool.contract?.outputs ?? []).map((o) => [o.name, sampleValue(o.type)]),
      ),
      timestamp: new Date().toISOString(),
    },
    null,
    2,
  );

  const n8n = `1. Open your n8n workspace.
2. Add a "Webhook" trigger node.
3. Paste the URL above as the production URL.
4. Set method = POST, response = JSON.`;

  const zapier = `1. Create a new Zap.
2. Trigger = "Webhooks by Zapier" → "Catch Hook".
3. Paste the URL above as the custom webhook URL.
4. Test trigger to capture the payload shape.`;

  const make = `1. Create a new scenario in Make.
2. Add a "Custom webhook" module.
3. Paste the URL above and click "Save".
4. Run once to capture the schema.`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Icon name="link" size={14} className="text-accent" aria-hidden />
          <code className="font-mono text-sm">{tool.webhookUrl}</code>
        </div>
        <p className="er-caption text-muted-foreground">
          Trigger this action from any automation platform that supports
          outbound webhooks.
        </p>
      </Card>
      <Card className="gap-2 p-4">
        <div className="flex items-center gap-2">
          <Icon name="arrowDown" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Sample payload</h4>
        </div>
        <CodeBlock code={samplePayload} language="json" />
      </Card>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {[
          { name: "n8n", icon: "iterations" as ErIconName, body: n8n },
          { name: "Zapier", icon: "workflow" as ErIconName, body: zapier },
          { name: "Make", icon: "sync" as ErIconName, body: make },
        ].map((g) => (
          <Card key={g.name} className="gap-2 p-4">
            <div className="flex items-center gap-2">
              <Icon name={g.icon} size={14} aria-hidden />
              <h4 className="text-sm font-medium">{g.name}</h4>
            </div>
            <pre className="er-scroll max-h-44 overflow-auto whitespace-pre-wrap er-caption text-muted-foreground">
              {g.body}
            </pre>
          </Card>
        ))}
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Registry tab — aggregate MCP server manifest                        */
/* ------------------------------------------------------------------ */

function RegistryTab() {
  const { data: reg, loading, error } = useApi<McpRegistry>(
    () => api.getMcpRegistry(),
    [],
  );

  if (loading) {
    return <Skeleton className="h-96 w-full" />;
  }
  if (error || !reg) {
    return (
      <EmptyState
        icon="publishing"
        title="Registry unavailable"
        description="The MCP registry will appear here once the backend is reachable."
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Registry summary */}
      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3">
            <span
              className="grid size-10 place-items-center rounded-md bg-primary text-primary-foreground"
            >
              <Icon name="server" size={20} aria-hidden />
            </span>
            <div>
              <p className="font-heading text-lg leading-tight">{reg.serverName}</p>
              <p className="er-caption text-muted-foreground">
                MCP server v{reg.serverVersion} · protocol {reg.protocolVersion}
              </p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Badge className="er-pill-primary">
              <Icon name="versions" size={12} aria-hidden /> {reg.tools.length} tools
            </Badge>
            <Badge className="er-pill-success">
              <Icon name="shieldCheck" size={12} aria-hidden /> live
            </Badge>
          </div>
        </div>
      </Card>

      {/* Tool index */}
      <div>
        <h3 className="er-h3 mb-3 flex items-center gap-2">
          <Icon name="tasklist" size={18} aria-hidden /> Tool index
        </h3>
        <Card className="overflow-hidden p-0">
          <div className="divide-y divide-border">
            {reg.registry.map((entry, i) => (
              <div
                key={entry.actionId}
                className="flex items-center gap-3 px-4 py-3 hover:bg-secondary/30"
              >
                <span className="er-caption text-muted-foreground w-6">#{i + 1}</span>
                <code className="font-mono text-sm text-foreground flex-1 truncate">
                  {entry.mcpToolName}
                </code>
                <Badge variant="outline" className="er-pill-neutral capitalize text-xs">
                  {entry.category}
                </Badge>
                <RiskBadge level={entry.riskLevel as "low" | "medium" | "high" | "critical"} />
                <span className="er-caption text-muted-foreground">v{entry.version}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Config snippets */}
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="er-h3 mb-3 flex items-center gap-2">
            <Icon name="hubot" size={18} aria-hidden /> Claude Desktop
          </h3>
          <CodeBlock code={reg.claudeConfig} language="json" />
          <p className="er-caption mt-2 text-muted-foreground">
            Paste into <code className="font-mono">~/Library/Application Support/Claude/claude_desktop_config.json</code>
          </p>
        </div>
        <div>
          <h3 className="er-h3 mb-3 flex items-center gap-2">
            <Icon name="terminal" size={18} aria-hidden /> Cursor
          </h3>
          <CodeBlock code={reg.cursorConfig} language="json" />
          <p className="er-caption mt-2 text-muted-foreground">
            Save as <code className="font-mono">.cursor/mcp.json</code> in your project root
          </p>
        </div>
      </div>

      <div>
        <h3 className="er-h3 mb-3 flex items-center gap-2">
          <Icon name="terminal" size={18} aria-hidden /> CLI install
        </h3>
        <CodeBlock code={reg.curlInstall} language="bash" />
      </div>

      {/* Full manifest */}
      <div>
        <h3 className="er-h3 mb-3 flex items-center gap-2">
          <Icon name="code" size={18} aria-hidden /> Full MCP manifest
        </h3>
        <CodeBlock code={JSON.stringify(reg.tools, null, 2)} language="json" />
      </div>
    </div>
  );
}

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
