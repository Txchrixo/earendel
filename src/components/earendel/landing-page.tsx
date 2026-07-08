"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Icon, type ErIconName } from "./icon";
import { cn } from "@/lib/utils";

interface LandingPageProps {
  onEnter: () => void;
  onAuth: () => void;
}

const PIPELINE = [
  { icon: "recorder" as ErIconName, step: "01", title: "Record", desc: "Capture an authorised human workflow once. DOM, network, screenshots, HAR — every signal." },
  { icon: "code" as ErIconName, step: "02", title: "Compile", desc: "LLM infers a typed action contract: inputs, outputs, preconditions, postconditions." },
  { icon: "shieldCheck" as ErIconName, step: "03", title: "Validate & repair", desc: "Canaries run continuously. Selectors drift? The repair loop proposes a patch." },
  { icon: "publishing" as ErIconName, step: "04", title: "Publish", desc: "MCP tool, REST endpoint, SDK function, webhook — one action, every surface." },
];

const FEATURES = [
  { icon: "iterations" as ErIconName, title: "Multi-adapter execution", desc: "Official API → discovered internal route → browser → vision → human review. The orchestrator picks the most reliable path automatically." },
  { icon: "beaker" as ErIconName, title: "Continuous validation", desc: "Canaries run every 15 minutes. Postconditions checked. Schema validated. You know it broke before your agents do." },
  { icon: "wrench" as ErIconName, title: "Self-healing selectors", desc: "When a UI changes, Earendel proposes a candidate selector with a confidence score. Approve the patch — or let it auto-apply above 90%." },
  { icon: "shield" as ErIconName, title: "Risk-gated autonomy", desc: "Read-only actions auto-run. Submit-level actions need confirmation. Destructive actions require typed approval. Never let an agent improvise." },
  { icon: "versions" as ErIconName, title: "API-style versioning", desc: "Every action is versioned (semver). Rollback instantly. Diff contracts between versions. Treat your automations like real APIs." },
  { icon: "server" as ErIconName, title: "MCP-native publishing", desc: "Publish as a Model Context Protocol tool. Claude, Cursor, Cline, Continue — any MCP-aware agent can call your actions." },
];

const STATS = [
  { value: "95%", label: "APISENSOR route-discovery precision" },
  { value: "82-96%", label: "Token reduction via AutoRPA synthesis" },
  { value: "30-40%", label: "RPA budget lost to maintenance (the problem we solve)" },
  { value: "<2s", label: "LLM-backed contract compilation" },
];

export function LandingPage({ onEnter, onAuth }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav */}
      <nav className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground">
              <Icon name="telescope" size={18} aria-hidden />
            </span>
            <span className="font-heading text-lg">Earendel</span>
          </div>
          <div className="hidden items-center gap-6 md:flex">
            <a href="#how" className="er-caption text-muted-foreground hover:text-foreground">How it works</a>
            <a href="#features" className="er-caption text-muted-foreground hover:text-foreground">Features</a>
            <a href="#research" className="er-caption text-muted-foreground hover:text-foreground">Research</a>
          </div>
          <Button size="sm" onClick={onAuth}>
            Sign in
          </Button>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-4 py-20 text-center md:py-32">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Badge className="er-pill-primary mb-6">
            <Icon name="sparkles" size={12} aria-hidden /> Reliability layer for agent-grade workflows
          </Badge>
          <h1 className="er-hero font-heading">
            Turn repeated human workflows into typed, monitored, repairable agent tools.
          </h1>
          <p className="er-body mx-auto mt-6 max-w-2xl text-muted-foreground">
            Businesses still run on portals built for humans, not agents. Earendel records
            those authorised workflows, compiles them into typed actions with inputs, outputs
            and tests, and publishes them as MCP tools your agents can call reliably.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button size="lg" onClick={onAuth}>
              <Icon name="plus" size={16} aria-hidden /> Get started free
            </Button>
            <Button size="lg" variant="outline" onClick={onEnter}>
              <Icon name="playground" size={16} aria-hidden /> Try the demo
            </Button>
          </div>
          <p className="er-caption mt-4 text-muted-foreground">
            No credit card. 6 seeded connectors ready to explore.
          </p>
        </motion.div>
      </section>

      {/* Stats strip */}
      <section className="border-y border-border bg-card/50">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-4 px-4 py-8 md:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <p className="font-heading text-3xl text-foreground">{s.value}</p>
              <p className="er-caption mt-1 text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-6xl px-4 py-20">
        <div className="mb-12 text-center">
          <h2 className="er-h1 font-heading">From a click to a callable tool</h2>
          <p className="er-body mx-auto mt-3 max-w-2xl text-muted-foreground">
            Four steps. One recorded workflow becomes a reliable, versioned, monitored action
            your agents call through MCP.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PIPELINE.map((p, i) => (
            <Card key={p.title} className="p-6">
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-muted-foreground">{p.step}</span>
                <span className="grid size-8 place-items-center rounded-md bg-secondary text-muted-foreground">
                  <Icon name={p.icon} size={16} aria-hidden />
                </span>
              </div>
              <h3 className="er-h3 mt-4">{p.title}</h3>
              <p className="er-caption mt-2 text-muted-foreground">{p.desc}</p>
              {i < PIPELINE.length - 1 && (
                <Icon name="arrowRight" size={16} className="mt-4 text-muted-foreground hidden lg:block" aria-hidden />
              )}
            </Card>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-border bg-card/30">
        <div className="mx-auto max-w-6xl px-4 py-20">
          <div className="mb-12 text-center">
            <h2 className="er-h1 font-heading">Built for reliability, not demos</h2>
            <p className="er-body mx-auto mt-3 max-w-2xl text-muted-foreground">
              The hard trade-off is that universal browser access is powerful but brittle.
              Earendel gives up full universality at runtime and focuses on maintained,
              typed actions with validation, telemetry and repair loops.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <Card key={f.title} className="p-6">
                <span className="grid size-10 place-items-center rounded-md bg-secondary text-muted-foreground">
                  <Icon name={f.icon} size={20} aria-hidden />
                </span>
                <h3 className="er-h3 mt-4">{f.title}</h3>
                <p className="er-caption mt-2 text-muted-foreground leading-relaxed">{f.desc}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Research-backed */}
      <section id="research" className="mx-auto max-w-4xl px-4 py-20 text-center">
        <h2 className="er-h1 font-heading">Grounded in research</h2>
        <p className="er-body mx-auto mt-3 max-w-2xl text-muted-foreground">
          Earendel implements the typed-actions thesis from recent systems research,
          combining program synthesis, vision-based UI parsing and traffic-based API
          discovery into one reliability discipline.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          {[
            "Web Verbs (arXiv 2602.17245)",
            "APISENSOR (arXiv 2603.23852)",
            "AutoRPA (ICML'26)",
            "OmniParser",
            "MCP (Anthropic, Nov 2024)",
          ].map((paper) => (
            <Badge key={paper} variant="outline" className="er-pill-neutral">
              {paper}
            </Badge>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border bg-card/30">
        <div className="mx-auto max-w-2xl px-4 py-20 text-center">
          <h2 className="er-h1 font-heading">Stop clicking. Start calling.</h2>
          <p className="er-body mx-auto mt-3 text-muted-foreground">
            Record your first workflow in under five minutes. Compile it to a typed action.
            Publish it as an MCP tool. Let your agents call it reliably.
          </p>
          <Button size="lg" className="mt-8" onClick={onAuth}>
            <Icon name="telescope" size={16} aria-hidden /> Enter the Studio
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border px-4 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-2">
            <span className="grid size-6 place-items-center rounded bg-primary text-primary-foreground">
              <Icon name="telescope" size={14} aria-hidden />
            </span>
            <span className="er-caption text-muted-foreground">Earendel · v0.1.0</span>
          </div>
          <div className="flex items-center gap-4 er-caption text-muted-foreground">
            <a className="hover:text-foreground" href="#">Docs</a>
            <a className="hover:text-foreground" href="#">GitHub</a>
            <a className="hover:text-foreground" href="#">MCP Registry</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
