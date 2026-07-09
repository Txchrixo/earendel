"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import type { McpRegistry } from "@/lib/earendel/types";
import { CodeBlock, EmptyState, RiskBadge } from "../primitives";

/* ------------------------------------------------------------------ */
/* Registry tab — aggregate MCP server manifest                        */
/* ------------------------------------------------------------------ */

export function RegistryTab() {
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
