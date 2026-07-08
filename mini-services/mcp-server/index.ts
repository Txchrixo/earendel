/**
 * Earendel MCP Server — Model Context Protocol server.
 *
 * Exposes all published Earendel typed actions as MCP tools that Claude
 * Desktop, Cursor, and any MCP-aware client can discover and call.
 *
 * Transport: SSE (Server-Sent Events) over HTTP — works across the Caddy
 * gateway with XTransformPort=3004.
 *
 * Protocol:
 *   POST /mcp  — JSON-RPC 2.0 requests (initialize, tools/list, tools/call)
 *   GET  /sse  — SSE stream for server-to-client notifications
 *
 * When a tool is called, the server forwards the request to the FastAPI
 * orchestrator (POST /api/v1/executions) which runs the action through
 * its multi-adapter fallback chain and returns the result.
 */
import { createServer } from "http";
import { readFileSync } from "fs";
import { createHmac } from "crypto";

const PORT = 3004;
const BACKEND_URL = "http://localhost:8001";
const BACKEND_PORT = "8001";

// Read BACKEND_SECRET from the project .env to mint JWTs for the FastAPI backend.
function getBackendSecret(): string {
  try {
    const env = readFileSync("/home/z/my-project/.env", "utf-8");
    for (const line of env.split("\n")) {
      if (line.startsWith("BACKEND_SECRET=")) {
        return line.split("=")[1].trim().replace(/^"|"$/g, "");
      }
    }
  } catch {}
  return "dev-secret-change-me";
}

function mintBackendToken(): string {
  const secret = getBackendSecret();
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    uid: "mcp-server",
    email: "mcp@earendel.io",
    iss: "earendel-studio",
    aud: "earendel-api",
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 86400 * 7,
  })).toString("base64url");
  const data = `${header}.${payload}`;
  const sig = createHmac("sha256", secret).update(data).digest("base64url");
  return `${data}.${sig}`;
}

let _cachedToken: string | null = null;
function getAuthToken(): string {
  if (!_cachedToken) {
    _cachedToken = mintBackendToken();
  }
  return _cachedToken;
}

// ---- Types ----

interface EarendelAction {
  id: string;
  name: string;
  signature: string;
  description: string;
  category: string;
  status: string;
  version: string;
  contract: {
    inputs: Array<{
      name: string;
      type: string;
      required: boolean;
      description?: string;
      enum?: string[];
    }>;
    outputs: Array<{ name: string; type: string; required: boolean }>;
  };
  mcpToolName?: string;
}

interface EarendelExecution {
  id: string;
  status: string;
  adapter: string;
  outputs?: Record<string, unknown>;
  errorMessage?: string;
  durationMs: number;
}

// ---- Backend API client ----

async function fetchActions(): Promise<EarendelAction[]> {
  const url = `${BACKEND_URL}/api/v1/actions?XTransformPort=${BACKEND_PORT}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${getAuthToken()}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch actions: ${res.status}`);
  return res.json();
}

async function runAction(
  actionId: string,
  inputs: Record<string, unknown>,
): Promise<EarendelExecution> {
  const url = `${BACKEND_URL}/api/v1/executions?XTransformPort=${BACKEND_PORT}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAuthToken()}`,
    },
    body: JSON.stringify({ actionId, inputs, caller: "agent" }),
  });
  if (!res.ok) throw new Error(`Failed to run action: ${res.status}`);
  return res.json();
}

// ---- JSON-RPC helpers ----

function jsonResponse(id: string | number | null, result: unknown) {
  return JSON.stringify({ jsonrpc: "2.0", id, result });
}

function errorResponse(id: string | number | null, code: number, message: string) {
  return JSON.stringify({ jsonrpc: "2.0", id, error: { code, message } });
}

// ---- MCP tool builder ----

function buildMcpTool(action: EarendelAction) {
  const toolName = action.mcpToolName || `earendel_${action.name.toLowerCase()}`;
  const properties: Record<string, unknown> = {};
  const required: string[] = [];

  for (const input of action.contract.inputs) {
    const prop: Record<string, unknown> = {
      type: input.type === "number" ? "number" : "string",
      description: input.description || input.name,
    };
    if (input.enum) {
      prop.enum = input.enum;
    }
    properties[input.name] = prop;
    if (input.required) {
      required.push(input.name);
    }
  }

  return {
    name: toolName,
    description: action.description,
    inputSchema: {
      type: "object" as const,
      properties,
      required,
    },
  };
}

// ---- HTTP server (JSON-RPC over HTTP POST) ----

const server = createServer(async (req, res) => {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Content-Type", "application/json");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // SSE endpoint (for clients that need server-push notifications)
  if (req.url === "/sse") {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    });
    res.write(`data: ${JSON.stringify({ type: "connected", server: "earendel-mcp" })}\n\n`);
    // Keep alive
    const interval = setInterval(() => {
      res.write(`: keepalive\n\n`);
    }, 30000);
    req.on("close", () => clearInterval(interval));
    return;
  }

  // Health check
  if (req.url === "/health") {
    res.writeHead(200);
    res.end(JSON.stringify({ status: "ok", server: "earendel-mcp", port: PORT }));
    return;
  }

  // MCP JSON-RPC endpoint
  if (req.url === "/mcp" && req.method === "POST") {
    let body = "";
    for await (const chunk of req) {
      body += chunk;
    }

    let rpcRequest: { jsonrpc: string; id?: string | number | null; method: string; params?: unknown };
    try {
      rpcRequest = JSON.parse(body);
    } catch {
      res.writeHead(400);
      res.end(errorResponse(null, -32700, "Parse error"));
      return;
    }

    const { id, method, params } = rpcRequest;

    try {
      // ---- initialize ----
      if (method === "initialize") {
        const result = {
          protocolVersion: "2024-11-05",
          capabilities: {
            tools: {},
          },
          serverInfo: {
            name: "earendel-mcp-server",
            version: "1.0.0",
          },
        };
        res.writeHead(200);
        res.end(jsonResponse(id, result));
        return;
      }

      // ---- tools/list ----
      if (method === "tools/list") {
        const actions = await fetchActions();
        const published = actions.filter(
          (a) => a.status === "published" || a.status === "testing",
        );
        const tools = published.map(buildMcpTool);
        res.writeHead(200);
        res.end(jsonResponse(id, { tools }));
        return;
      }

      // ---- tools/call ----
      if (method === "tools/call") {
        const callParams = params as {
          name: string;
          arguments?: Record<string, unknown>;
        };

        // Find the action by tool name
        const actions = await fetchActions();
        const action = actions.find(
          (a) =>
            (a.mcpToolName || `earendel_${a.name.toLowerCase()}`) ===
            callParams.name,
        );

        if (!action) {
          res.writeHead(200);
          res.end(
            errorResponse(id, -32602, `Unknown tool: ${callParams.name}`),
          );
          return;
        }

        // Run the action via the orchestrator
        const execution = await runAction(
          action.id,
          callParams.arguments || {},
        );

        // Format the result as MCP content
        let content: string;
        if (execution.status === "success") {
          content = JSON.stringify(execution.outputs, null, 2);
        } else if (execution.status === "human_review") {
          content = `Action requires human review. Review ID: ${(execution.outputs as Record<string, unknown>)?.reviewId || "unknown"}`;
        } else {
          content = `Action failed: ${execution.errorMessage || "unknown error"}`;
        }

        const result = {
          content: [{ type: "text", text: content }],
          isError: execution.status !== "success",
        };
        res.writeHead(200);
        res.end(jsonResponse(id, result));
        return;
      }

      // ---- ping ----
      if (method === "ping") {
        res.writeHead(200);
        res.end(jsonResponse(id, {}));
        return;
      }

      // Unknown method
      res.writeHead(200);
      res.end(errorResponse(id, -32601, `Method not found: ${method}`));
    } catch (err) {
      console.error("MCP request error:", err);
      res.writeHead(500);
      res.end(
        errorResponse(id, -32603, `Internal error: ${err}`),
      );
    }
    return;
  }

  // Default: 404
  res.writeHead(404);
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(PORT, () => {
  console.log(`Earendel MCP Server running on port ${PORT}`);
  console.log(`  JSON-RPC: POST http://localhost:${PORT}/mcp`);
  console.log(`  SSE:      GET  http://localhost:${PORT}/sse`);
  console.log(`  Health:   GET  http://localhost:${PORT}/health`);
});

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("Shutting down MCP server...");
  server.close(() => process.exit(0));
});
process.on("SIGINT", () => {
  console.log("Shutting down MCP server...");
  server.close(() => process.exit(0));
});
