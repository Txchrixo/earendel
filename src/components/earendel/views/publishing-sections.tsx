"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Icon, type ErIconName } from "../icon";
import type { PublishedTool } from "@/lib/earendel/types";
import { CodeBlock } from "../primitives";

/* ------------------------------------------------------------------ */
/* The backend returns a richer shape than the shared TS type, so we  */
/* narrow locally without modifying types.ts.                         */
/* ------------------------------------------------------------------ */

export interface RichPublishedTool extends PublishedTool {
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
          <Button size="sm" variant="outline" className="rounded-full" onClick={copyRegistry}>
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
          now callable by any MCP-aware agent - inputs are validated against the
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

  // The canonical run endpoint is POST /api/v1/executions with body
  // { actionId, inputs }. There is no per-action REST route; every
  // published action is invoked through this single endpoint.
  const endpointPath = "/api/v1/executions";
  const endpointUrl = `https://api.earendel.io${endpointPath}`;

  const inputsObj = Object.fromEntries(
    inputs.map((i) => [i.name, sampleValue(i.type)]),
  );
  const requestBody = {
    actionId: tool.actionId,
    inputs: inputsObj,
  };
  const requestBodyJson = JSON.stringify(requestBody, null, 2);

  const bodySchema = JSON.stringify(
    {
      type: "object",
      properties: {
        actionId: { type: "string", description: "Id of the published action to run" },
        inputs: {
          type: "object",
          properties: Object.fromEntries(
            inputs.map((i) => [i.name, { type: i.type, description: i.description }]),
          ),
          required: inputs.filter((i) => i.required).map((i) => i.name),
        },
      },
      required: ["actionId", "inputs"],
    },
    null,
    2,
  );

  const sampleResponse = JSON.stringify(
    {
      executionId: "exe_sample",
      actionId: tool.actionId,
      actionName: name,
      status: "success",
      outputs: Object.fromEntries(outputs.map((o) => [o.name, sampleValue(o.type)])),
    },
    null,
    2,
  );

  const curl = `curl -X POST '${endpointUrl}' \\
  -H 'Authorization: Bearer $EARENDEL_API_KEY' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify(requestBody)}'`;

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
          <code className="font-mono text-sm">{endpointPath}</code>
        </div>
        <p className="er-caption text-muted-foreground">
          Canonical run endpoint for {name}. POST {"{"}actionId, inputs{"}"} to
          start an execution; returns the created execution with its outputs
          (or 422 on contract violation).
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
      <Card className="gap-2 p-4">
        <div className="flex items-center gap-2">
          <Icon name="copy" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Request body for this action</h4>
        </div>
        <CodeBlock code={requestBodyJson} language="json" />
      </Card>
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
  const inputs = tool.contract?.inputs ?? [];
  const outputs = tool.contract?.outputs ?? [];

  // SDK packages are not published yet. Show the real REST contract
  // (POST /api/v1/executions) so callers can integrate today.
  const endpointUrl = "https://api.earendel.io/api/v1/executions";
  const requestBody = {
    actionId: tool.actionId,
    inputs: Object.fromEntries(
      inputs.map((i) => [i.name, sampleValue(i.type)]),
    ),
  };
  const requestBodyJson = JSON.stringify(requestBody, null, 2);

  const ts = `// No @earendel/sdk package yet - call the REST endpoint directly.
// SDK packages are planned. Use the REST API or MCP server for now.

const res = await fetch("${endpointUrl}", {
  method: "POST",
  headers: {
    "Authorization": \`Bearer \${process.env.EARENDEL_API_KEY}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify(${JSON.stringify(requestBody)}),
});

const execution = await res.json();
console.log(execution.outputs);
// → { ${outputs.map((o) => o.name).join(", ")} }`;

  const py = `# No earendel-sdk package yet - call the REST endpoint directly.
# SDK packages are planned. Use the REST API or MCP server for now.

import os, requests

res = requests.post(
    "${endpointUrl}",
    headers={
        "Authorization": f"Bearer {os.environ['EARENDEL_API_KEY']}",
        "Content-Type": "application/json",
    },
    json=${JSON.stringify(requestBody)},
)

execution = res.json()
print(execution["outputs"])
# → { ${outputs.map((o) => o.name).join(", ")} }`;

  const [lang, setLang] = React.useState<"typescript" | "python">("typescript");
  const args = inputs.map((i) => `${i.name}: ${tsType(i.type)}`).join(", ");
  void args;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-2 border-accent/30 bg-accent/5 p-4">
        <div className="flex items-center gap-2">
          <Icon name="lightbulb" size={14} className="text-chart-4" aria-hidden />
          <h4 className="text-sm font-medium">SDK packages are planned</h4>
        </div>
        <p className="er-caption text-muted-foreground">
          SDK packages are planned. Use the REST API or MCP server for now.
          The snippets below call POST /api/v1/executions, the canonical
          entry point for running any published action.
        </p>
      </Card>
      <Card className="gap-2 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Icon name="code" size={14} aria-hidden />
            <h4 className="text-sm font-medium">Run {name}</h4>
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
        <CodeBlock
          code={lang === "typescript" ? ts : py}
          language={lang === "typescript" ? "typescript" : "python"}
        />
      </Card>
      <Card className="gap-2 p-4">
        <div className="flex items-center gap-2">
          <Icon name="arrowDown" size={14} aria-hidden />
          <h4 className="text-sm font-medium">Request body</h4>
        </div>
        <CodeBlock code={requestBodyJson} language="json" />
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
  void tool;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-4"
    >
      <Card className="gap-2 border-accent/30 bg-accent/5 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Icon name="link" size={14} className="text-accent" aria-hidden />
          <Badge variant="outline" className="er-caption">Coming soon</Badge>
        </div>
        <p className="er-caption text-muted-foreground">
          Outbound webhooks for action.completed events are on the roadmap
          and no webhook route exists yet. For now, poll
          GET /api/v1/executions/{"{executionId}"} or subscribe to the
          execution SSE stream for real-time status updates.
        </p>
      </Card>
    </motion.div>
  );
}

export { McpTab, RestTab, SdkTab, WebhookTab };
