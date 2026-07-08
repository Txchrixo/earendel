"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Icon, type ErIconName } from "./icon";

/* ------------------------------------------------------------------ */
/* InteractiveAgentPreview — a faux browser window with a live mini   */
/* Earendel studio inside. Users can search actions, "run" them, and  */
/* see the agent compose tool calls — all on the landing page.        */
/* ------------------------------------------------------------------ */

interface MiniAction {
  id: string;
  name: string;
  signature: string;
  category: string;
  icon: ErIconName;
}

const DEMO_ACTIONS: MiniAction[] = [
  { id: "1", name: "downloadInvoice", signature: "downloadInvoice(invoiceId)", category: "finance", icon: "download" },
  { id: "2", name: "trackShipment", signature: "trackShipment(carrier, trackingNumber)", category: "logistics", icon: "package" },
  { id: "3", name: "checkClaimStatus", signature: "checkClaimStatus(patientId, claimId)", category: "healthcare", icon: "law" },
  { id: "4", name: "downloadMarketplaceReport", signature: "downloadMarketplaceReport(marketplace, reportType)", category: "ecommerce", icon: "graph" },
];

interface ChatMessage {
  role: "agent" | "user" | "system" | "tool";
  content: string;
  toolName?: string;
  toolResult?: string;
}

const INITIAL_MESSAGES: ChatMessage[] = [
  { role: "system", content: "You have access to Earendel published typed actions as MCP tools. Call them with inputs; outputs are validated and logged." },
  { role: "user", content: "Download invoices INV-1001 and INV-1002, then tell me the total." },
];

const PRESET_PROMPTS = [
  "Download invoices INV-1001 and INV-1002",
  "Track shipment MAEU-8842 with Maersk",
  "Check claim status for patient PAT-501",
];

export function InteractiveAgentPreview() {
  const [messages, setMessages] = React.useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [input, setInput] = React.useState("");
  const [running, setRunning] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [activeAction, setActiveAction] = React.useState<MiniAction | null>(null);
  const chatRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const runAgent = async (prompt: string) => {
    setRunning(true);
    setMessages((prev) => [...prev, { role: "user", content: prompt }]);
    setInput("");

    // Simulate agent thinking
    await sleep(600);
    setMessages((prev) => [...prev, { role: "agent", content: "I'll call the typed actions for you. No browser clicking needed." }]);

    // Parse the prompt for action calls
    const invoiceMatch = prompt.match(/INV-\d+/gi);
    const shipmentMatch = prompt.match(/MAEU-\d+/i);
    const claimMatch = prompt.match(/PAT-\d+/i);

    if (invoiceMatch) {
      let total = 0;
      for (const inv of invoiceMatch.slice(0, 3)) {
        await sleep(800);
        const amount = 4280.50;
        total += amount;
        setMessages((prev) => [
          ...prev,
          { role: "tool", toolName: `downloadInvoice("${inv}")`, toolResult: `success · €${amount.toFixed(2)}` },
        ]);
      }
      await sleep(400);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Done. ${invoiceMatch.length} invoice(s) downloaded. Total amount: €${total.toFixed(2)}.` },
      ]);
    } else if (shipmentMatch) {
      await sleep(1000);
      setMessages((prev) => [
        ...prev,
        { role: "tool", toolName: `trackShipment("maersk", "${shipmentMatch[0]}")`, toolResult: "success · in_transit · ETA 2025-02-14" },
      ]);
      await sleep(400);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Shipment is in transit. Current location: Rotterdam, NL. ETA: February 14." },
      ]);
    } else if (claimMatch) {
      await sleep(1000);
      setMessages((prev) => [
        ...prev,
        { role: "tool", toolName: `checkClaimStatus("PAT-501", "CLM-7782")`, toolResult: "success · denied · missing prior authorization" },
      ]);
      await sleep(400);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Claim was denied. Reason: missing prior authorization. Recommended next step: resubmit with PA document." },
      ]);
    } else {
      await sleep(600);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "I can download invoices, track shipments, or check claim statuses. Try one of the preset prompts below." },
      ]);
    }

    setRunning(false);
  };

  const filteredActions = searchQuery
    ? DEMO_ACTIONS.filter((a) => a.name.toLowerCase().includes(searchQuery.toLowerCase()) || a.category.includes(searchQuery.toLowerCase()))
    : DEMO_ACTIONS;

  return (
    <div className="flex h-[560px] overflow-hidden rounded-lg border border-border bg-card">
      {/* Left: action catalog + search */}
      <div className="hidden w-56 shrink-0 flex-col border-r border-border bg-sidebar sm:flex">
        <div className="border-b border-border p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="grid size-6 place-items-center rounded bg-primary text-primary-foreground">
              <Icon name="telescope" size={14} aria-hidden />
            </span>
            <span className="font-heading text-sm">Earendel</span>
          </div>
          <div className="relative">
            <Icon name="search" size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search actions…"
              className="h-7 pl-7 text-xs"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto er-scroll p-2 space-y-1">
          <p className="er-caption text-muted-foreground uppercase tracking-wide px-1 py-1">Typed actions</p>
          {filteredActions.map((a) => (
            <button
              key={a.id}
              onClick={() => setActiveAction(a)}
              className={cn(
                "flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors",
                activeAction?.id === a.id ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/50",
              )}
            >
              <Icon name={a.icon} size={12} className="mt-0.5 shrink-0 text-accent" aria-hidden />
              <div className="min-w-0">
                <p className="font-mono truncate">{a.name}</p>
                <p className="er-caption text-muted-foreground truncate">{a.category}</p>
              </div>
            </button>
          ))}
          {filteredActions.length === 0 && (
            <p className="er-caption text-muted-foreground px-2 py-4 text-center">No actions found.</p>
          )}
        </div>
        <div className="border-t border-border p-2">
          <div className="flex items-center gap-1.5 er-caption text-muted-foreground">
            <span className="size-1.5 rounded-full bg-accent er-pulse" aria-hidden />
            4 tools · MCP live
          </div>
        </div>
      </div>

      {/* Right: agent chat */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Chat header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-2">
          <div className="flex items-center gap-2">
            <Icon name="playground" size={14} className="text-accent" aria-hidden />
            <span className="text-sm font-medium">Agent Playground</span>
          </div>
          <Badge className="er-pill-success text-[10px]">
            <span className="size-1 rounded-full bg-accent er-pulse mr-1" aria-hidden />
            connected
          </Badge>
        </div>

        {/* Chat messages */}
        <div ref={chatRef} className="flex-1 overflow-y-auto er-scroll px-4 py-3 space-y-3">
          {messages.map((msg, i) => {
            if (msg.role === "system") {
              return (
                <div key={i} className="rounded-md border border-border bg-secondary/50 p-2.5 text-xs text-muted-foreground">
                  {msg.content}
                </div>
              );
            }
            if (msg.role === "user") {
              return (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[80%] rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground">
                    {msg.content}
                  </div>
                </div>
              );
            }
            if (msg.role === "tool") {
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-md border border-border bg-background p-2.5"
                >
                  <div className="flex items-center gap-2">
                    <Icon name="executions" size={12} className="text-accent shrink-0" aria-hidden />
                    <code className="font-mono text-xs text-foreground">{msg.toolName}</code>
                  </div>
                  <p className="mt-1 text-xs text-accent font-mono">{msg.toolResult}</p>
                </motion.div>
              );
            }
            // agent
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-start gap-2"
              >
                <span className="grid size-6 place-items-center rounded bg-secondary text-muted-foreground shrink-0">
                  <Icon name="robot" size={12} aria-hidden />
                </span>
                <div className="max-w-[80%] rounded-md bg-secondary px-3 py-1.5 text-xs text-foreground">
                  {msg.content}
                </div>
              </motion.div>
            );
          })}
          {running && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Icon name="sync" size={12} className="er-pulse" aria-hidden />
              thinking…
            </div>
          )}
        </div>

        {/* Preset prompts */}
        {messages.length <= 2 && !running && (
          <div className="flex flex-wrap gap-1.5 px-4 pb-2">
            {PRESET_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => runAgent(p)}
                className="rounded-md border border-border bg-secondary/50 px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
              >
                {p}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="border-t border-border p-3">
          <div className="flex items-center gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && input.trim() && !running) {
                  e.preventDefault();
                  runAgent(input);
                }
              }}
              placeholder="Message the agent…"
              disabled={running}
              className="text-xs"
            />
            <Button
              size="sm"
              onClick={() => input.trim() && !running && runAgent(input)}
              disabled={running || !input.trim()}
            >
              <Icon name="arrowRight" size={12} aria-hidden />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export default InteractiveAgentPreview;
