"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import type { TypedAction, Execution } from "@/lib/earendel/types";
import { SectionTitle, EmptyState, AdapterChip } from "../primitives";
import { RiskGateDialog } from "../risk-gate-dialog";

/* ------------------------------------------------------------------ */
/* Types                                                              */
/* ------------------------------------------------------------------ */

type CallStatus = "queued" | "running" | "success" | "failed";

interface ToolCall {
  id: string;
  signature: string;
  status: CallStatus;
  execution?: Execution;
}

interface Message {
  id: string;
  role: "system" | "user" | "agent";
  text: string;
  calls?: ToolCall[];
  thinking?: boolean;
}

/* ------------------------------------------------------------------ */
/* Available tools panel (right)                                      */
/* ------------------------------------------------------------------ */

function ToolsPanel({ actions }: { actions: TypedAction[] }) {
  const published = actions.filter((a) => a.publishedAs.includes("mcp"));
  return (
    <Card className="gap-3 p-4">
      <div className="flex items-center gap-2">
        <Icon name="package" size={14} className="text-accent" aria-hidden />
        <h3 className="er-h3">Available tools</h3>
        <Badge variant="secondary" className="ml-auto">
          {published.length} MCP
        </Badge>
      </div>
      <ul className="space-y-1.5">
        {published.length === 0 && (
          <li className="er-caption text-muted-foreground">
            No published actions yet.
          </li>
        )}
        {published.map((a) => (
          <li
            key={a.id}
            className="rounded-md border border-border bg-secondary/40 px-2.5 py-1.5"
          >
            <div className="flex items-center gap-2">
              <Icon name="robot" size={12} className="text-accent" aria-hidden />
              <code className="font-mono text-xs">{a.mcpToolName ?? a.name}</code>
            </div>
            <p className="er-caption mt-0.5 line-clamp-2 text-muted-foreground">
              {a.description}
            </p>
          </li>
        ))}
      </ul>
      <div className="rounded-md border border-accent/30 bg-accent/5 p-3">
        <p className="er-caption text-muted-foreground">
          The agent never opens a browser. It calls typed actions with inputs,
          outputs, permissions and logs. Fragile clicking is replaced by
          reliable, auditable function calls.
        </p>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Tool call card                                                     */
/* ------------------------------------------------------------------ */

function ToolCallCard({ call }: { call: ToolCall }) {
  const openExecution = useStudio((s) => s.openExecution);
  const statusIcon: Record<CallStatus, ErIconName> = {
    queued: "clock",
    running: "sync",
    success: "checkCircleFill",
    failed: "xCircleFill",
  };
  const statusColor: Record<CallStatus, string> = {
    queued: "text-muted-foreground",
    running: "text-primary",
    success: "text-accent",
    failed: "text-destructive",
  };
  const amount = call.execution?.outputs?.amount as number | undefined;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-md border border-border bg-secondary/40 p-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Icon
          name={statusIcon[call.status]}
          size={12}
          className={cn(statusColor[call.status], call.status === "running" && "er-pulse")}
          aria-hidden
        />
        <code className="font-mono text-xs">{call.signature}</code>
        <Badge variant="outline" className="er-caption capitalize">
          {call.status}
        </Badge>
        {call.execution && (
          <>
            <AdapterChip adapter={call.execution.adapter} />
            <span className="er-caption text-muted-foreground">
              {call.execution.durationMs}ms
            </span>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 px-2 er-caption"
              onClick={() => openExecution(call.execution!.id)}
            >
              <Icon name="graph" size={11} aria-hidden /> trace
            </Button>
          </>
        )}
      </div>
      {call.execution?.status === "success" && amount !== undefined && (
        <p className="er-caption mt-1 text-muted-foreground">
          → invoice {String(call.execution.outputs?.invoiceNumber)} ·{" "}
          <span className="text-foreground tabular-nums">
            €{amount.toFixed(2)}
          </span>
        </p>
      )}
      {call.execution?.status === "failed" && call.execution.errorMessage && (
        <p className="er-caption mt-1 text-destructive">
          {call.execution.errorMessage}
        </p>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Message bubble                                                     */
/* ------------------------------------------------------------------ */

function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === "system") {
    return (
      <div className="rounded-md border border-border bg-secondary/40 p-3">
        <div className="flex items-center gap-2">
          <Icon name="shieldCheck" size={12} className="text-accent" aria-hidden />
          <span className="er-caption font-medium">System</span>
        </div>
        <p className="er-caption mt-1 text-muted-foreground">{msg.text}</p>
      </div>
    );
  }
  if (msg.role === "user") {
    return (
      <div className="ml-auto max-w-[85%] rounded-md border border-primary/40 bg-primary/15 p-3">
        <div className="flex items-center gap-2">
          <Icon name="person" size={12} aria-hidden />
          <span className="er-caption font-medium">You</span>
        </div>
        <p className="mt-1 text-sm">{msg.text}</p>
      </div>
    );
  }
  return (
    <div className="mr-auto max-w-[90%] rounded-md border border-border bg-card p-3">
      <div className="flex items-center gap-2">
        <Icon name="hubot" size={12} className="text-accent" aria-hidden />
        <span className="er-caption font-medium">Agent</span>
      </div>
      {msg.thinking && (
        <div className="mt-2 flex items-center gap-2 er-caption text-muted-foreground">
          <Icon name="sync" size={12} className="er-pulse" aria-hidden />
          thinking…
        </div>
      )}
      {msg.calls && msg.calls.length > 0 && (
        <div className="mt-2 space-y-2">
          {msg.calls.map((c) => (
            <ToolCallCard key={c.id} call={c} />
          ))}
        </div>
      )}
      {msg.text && <p className="mt-2 text-sm">{msg.text}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Manual action runner                                               */
/* ------------------------------------------------------------------ */

function ManualRunner({ actions }: { actions: TypedAction[] }) {
  const [actionId, setActionId] = React.useState<string>(actions[0]?.id ?? "");
  const action = actions.find((a) => a.id === actionId) ?? actions[0];
  const [values, setValues] = React.useState<Record<string, string>>({});
  const [running, setRunning] = React.useState(false);
  const [result, setResult] = React.useState<Execution | null>(null);
  const openExecution = useStudio((s) => s.openExecution);

  React.useEffect(() => {
    if (actions.length && !actionId) setActionId(actions[0].id);
  }, [actions, actionId]);

  if (!action) {
    return (
      <Card className="gap-2 p-4">
        <p className="er-caption text-muted-foreground">No actions available.</p>
      </Card>
    );
  }

  const run = async () => {
    setRunning(true);
    setResult(null);
    try {
      const inputs: Record<string, unknown> = {};
      for (const f of action.contract.inputs) {
        const v = values[f.name];
        if (v === undefined || v === "") continue;
        inputs[f.name] = f.type === "number" ? Number(v) : v;
      }
      const exec = await api.runAction(action.id, inputs, "manual");
      setResult(exec);
      toast.success("Action ran", {
        description: `${action.name} → ${exec.status} (${exec.durationMs}ms)`,
      });
    } catch {
      toast.error("Run failed", { description: "Backend unreachable." });
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card className="gap-3 p-4">
      <div className="flex items-center gap-2">
        <Icon name="terminal" size={14} aria-hidden />
        <h3 className="text-sm font-medium">Manual action runner</h3>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <Select value={actionId || undefined} onValueChange={setActionId}>
          <SelectTrigger className="w-full" aria-label="Select action">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {actions.map((a) => (
              <SelectItem key={a.id} value={a.id}>
                {a.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <RiskGateDialog
          riskLevel={action.riskLevel}
          permission={action.permissions}
          actionLabel={action.signature}
          inputs={Object.fromEntries(
            Object.entries(values).filter(([, v]) => v !== "" && v !== undefined),
          )}
          onConfirm={run}
        >
          <Button disabled={running}>
            <Icon name="executions" size={14} aria-hidden />
            {running ? "Running…" : "Run action"}
          </Button>
        </RiskGateDialog>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {action.contract.inputs.map((f) => (
          <div key={f.name} className="flex flex-col gap-1">
            <Label htmlFor={`mf-${f.name}`} className="er-caption text-muted-foreground">
              {f.name}
              {f.required && <span className="ml-0.5 text-destructive">*</span>}
              <span className="ml-1 text-muted-foreground">({f.type})</span>
            </Label>
            <Input
              id={`mf-${f.name}`}
              value={values[f.name] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              placeholder={f.description ?? f.name}
            />
          </div>
        ))}
      </div>
      {result && (
        <div className="rounded-md border border-border bg-secondary/40 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              className={
                result.status === "success"
                  ? "bg-accent text-accent-foreground"
                  : "bg-destructive text-white"
              }
            >
              {result.status}
            </Badge>
            <AdapterChip adapter={result.adapter} />
            <span className="er-caption text-muted-foreground">
              {result.durationMs}ms
            </span>
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto h-6 px-2 er-caption"
              onClick={() => openExecution(result.id)}
            >
              View full trace <Icon name="arrowRight" size={11} aria-hidden />
            </Button>
          </div>
          <pre className="er-scroll mt-2 max-h-40 overflow-auto rounded-md bg-background/60 p-2 font-mono text-xs">
            {JSON.stringify(result.outputs ?? {}, null, 2)}
          </pre>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Agent chat (left)                                                  */
/* ------------------------------------------------------------------ */

const SAMPLE_PROMPT =
  "Download invoices INV-1001, INV-1002 and INV-1003, then tell me the total amount.";

function extractInvoiceIds(text: string): string[] {
  const matches = text.match(/INV-\d+/gi);
  return matches ?? [];
}

function AgentChat({ actions }: { actions: TypedAction[] }) {
  const [input, setInput] = React.useState(SAMPLE_PROMPT);
  const [messages, setMessages] = React.useState<Message[]>([
    {
      id: "sys",
      role: "system",
      text: "You have access to Earendel published typed actions as MCP tools. Call them with inputs; outputs are validated and logged. Do not improvise browser steps.",
    },
  ]);
  const [busy, setBusy] = React.useState(false);
  const downloadAction = actions.find((a) => a.name === "downloadInvoice") ?? actions[0];
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || !downloadAction || busy) return;
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      text: input,
    };
    const thinkingId = `t-${Date.now()}`;
    setMessages((m) => [
      ...m,
      userMsg,
      { id: thinkingId, role: "agent", text: "", thinking: true },
    ]);
    setBusy(true);

    const invoiceIds = extractInvoiceIds(input);
    const calls: ToolCall[] =
      invoiceIds.length > 0
        ? invoiceIds.map((id) => ({
            id: `c-${id}-${Date.now()}`,
            signature: `${downloadAction.name}("${id}")`,
            status: "queued" as CallStatus,
          }))
        : [];

    // simulate thinking pause
    await new Promise((r) => setTimeout(r, 700));

    if (calls.length === 0) {
      setMessages((m) =>
        m
          .filter((x) => x.id !== thinkingId)
          .concat({
            id: `a-${Date.now()}`,
            role: "agent",
            text: "I couldn't find any invoice ids in your message. Try “Download invoices INV-1001 and INV-1002”.",
          }),
      );
      setBusy(false);
      return;
    }

    const agentMsgId = `a-${Date.now()}`;
    setMessages((m) =>
      m
        .filter((x) => x.id !== thinkingId)
        .concat({ id: agentMsgId, role: "agent", text: "", calls }),
    );

    // run calls sequentially
    for (let i = 0; i < calls.length; i++) {
      const call = calls[i];
      const invoiceId = invoiceIds[i];
      // mark running
      setMessages((m) =>
        m.map((x) =>
          x.id === agentMsgId && x.calls
            ? {
                ...x,
                calls: x.calls.map((c) =>
                  c.id === call.id ? { ...c, status: "running" } : c,
                ),
              }
            : x,
        ),
      );
      try {
        const exec = await api.runAction(
          downloadAction.id,
          { invoiceId },
          "agent",
        );
        setMessages((m) =>
          m.map((x) =>
            x.id === agentMsgId && x.calls
              ? {
                  ...x,
                  calls: x.calls.map((c) =>
                    c.id === call.id
                      ? { ...c, status: exec.status === "success" ? "success" : "failed", execution: exec }
                      : c,
                  ),
                }
              : x,
          ),
        );
      } catch {
        setMessages((m) =>
          m.map((x) =>
            x.id === agentMsgId && x.calls
              ? {
                  ...x,
                  calls: x.calls.map((c) =>
                    c.id === call.id ? { ...c, status: "failed" } : c,
                  ),
                }
              : x,
          ),
        );
      }
    }

    // final summary
    const finalCalls = await new Promise<ToolCall[]>((resolve) => {
      setMessages((m) => {
        const target = m.find((x) => x.id === agentMsgId);
        resolve(target?.calls ?? []);
        return m;
      });
    });
    const total = finalCalls
      .filter((c) => c.execution?.outputs?.amount !== undefined)
      .reduce((sum, c) => sum + (c.execution!.outputs!.amount as number), 0);
    setMessages((m) =>
      m.map((x) =>
        x.id === agentMsgId
          ? {
              ...x,
              text: `Done. ${finalCalls.length} invoice(s) downloaded. Total amount: €${total.toFixed(2)}.`,
            }
          : x,
      ),
    );
    setBusy(false);
  };

  return (
    <Card className="gap-3 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon name="hubot" size={14} className="text-accent" aria-hidden />
          <h3 className="er-h3">Agent session</h3>
        </div>
        <Badge variant="outline" className="er-caption">
          <Icon name="robot" size={10} aria-hidden /> MCP
        </Badge>
      </div>
      <div
        ref={scrollRef}
        className="er-scroll flex max-h-[28rem] flex-col gap-2.5 overflow-y-auto pr-1"
      >
        {messages.map((m) => (
          <MessageBubble key={m.id} msg={m} />
        ))}
      </div>
      <div className="flex flex-col gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the agent to call a published action…"
          aria-label="Message the agent"
          rows={3}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              send();
            }
          }}
        />
        <div className="flex items-center justify-between">
          <span className="er-caption text-muted-foreground">
            ⌘ + Enter to send
          </span>
          <Button onClick={send} disabled={busy || !input.trim()}>
            <Icon name="comment" size={14} aria-hidden />
            {busy ? "Working…" : "Send"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* PlaygroundView                                                     */
/* ------------------------------------------------------------------ */

export function PlaygroundView() {
  const { data, loading, error } = useApi<TypedAction[]>(() => api.listActions(), []);
  const actions = data ?? [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="playground"
        title="Agent Playground"
        subtitle="Watch an agent compose typed actions. No clicking. No improvising. Just calls."
      />
      {error ? (
        <EmptyState
          icon="alert"
          title="Backend connecting…"
          description="The playground will populate once the FastAPI service is reachable."
        />
      ) : loading ? (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : actions.length === 0 ? (
        <EmptyState
          icon="actions"
          title="No actions published"
          description="Compile a recording and publish it to call it from the playground."
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
          <div className="flex flex-col gap-4">
            <AgentChat actions={actions} />
            <ManualRunner actions={actions} />
          </div>
          <ToolsPanel actions={actions} />
        </div>
      )}

    </motion.div>
  );
}

export default PlaygroundView;
