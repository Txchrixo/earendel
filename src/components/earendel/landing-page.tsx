"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Icon, type ErIconName } from "./icon";
import { InteractiveAgentPreview } from "./interactive-agent-preview";

interface LandingPageProps {
  onEnter: () => void;
  onAuth: () => void;
  onSignUp: () => void;
}

const PIPELINE = [
  { icon: "recorder" as ErIconName, step: "01", title: "Record", desc: "Capture an authorised human workflow once. DOM, network, screenshots, HAR — every signal." },
  { icon: "code" as ErIconName, step: "02", title: "Compile", desc: "LLM infers a typed action contract: inputs, outputs, preconditions, postconditions." },
  { icon: "shieldCheck" as ErIconName, step: "03", title: "Validate & repair", desc: "Canaries run continuously. Selectors drift? The repair loop proposes a patch." },
  { icon: "publishing" as ErIconName, step: "04", title: "Publish", desc: "MCP tool, REST endpoint, SDK function, webhook — one action, every surface." },
];

const FEATURES = [
  { icon: "iterations" as ErIconName, title: "Multi-adapter execution", desc: "Official API → discovered internal route → local browser → Browser Use cloud (optional) → vision → human review. The orchestrator picks the most reliable path automatically." },
  { icon: "beaker" as ErIconName, title: "Continuous validation", desc: "Canaries run every 15 minutes. Postconditions checked. Schema validated. You know it broke before your agents do." },
  { icon: "wrench" as ErIconName, title: "Self-healing selectors", desc: "When a UI changes, Earendel proposes a candidate selector with a confidence score. Approve the patch — or let it auto-apply above 90%." },
  { icon: "shield" as ErIconName, title: "Risk-gated autonomy", desc: "Read-only actions auto-run. Submit-level actions need confirmation. Destructive actions require typed approval. Never let an agent improvise." },
  { icon: "versions" as ErIconName, title: "API-style versioning", desc: "Every action is versioned (semver). Rollback instantly. Diff contracts between versions. Treat your automations like real APIs." },
  { icon: "server" as ErIconName, title: "MCP-native publishing", desc: "Publish as a Model Context Protocol tool. Claude, Cursor, Cline, Continue — any MCP-aware agent can call your actions." },
];

const STATS = [
  { value: "95%", label: "Route-discovery precision" },
  { value: "82-96%", label: "Token reduction via synthesis" },
  { value: "30-40%", label: "RPA budget lost to maintenance" },
  { value: "<2s", label: "LLM-backed compilation" },
];

export function LandingPage({ onEnter, onAuth, onSignUp }: LandingPageProps) {
  const router = useRouter();

  // Nav: transparent at top, solid bg on scroll (no border ever)
  React.useEffect(() => {
    const nav = document.getElementById("landing-nav");
    if (!nav) return;
    const onScroll = () => {
      if (window.scrollY > 20) {
        nav.style.background = "rgba(31, 26, 23, 0.85)";
        nav.style.backdropFilter = "blur(12px)";
      } else {
        nav.style.background = "transparent";
        nav.style.backdropFilter = "none";
      }
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Animated mouse-follow glow on the hero
  const heroRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;
    const onMove = (e: MouseEvent) => {
      const rect = hero.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      hero.style.setProperty("--mx", `${x}%`);
      hero.style.setProperty("--my", `${y}%`);
    };
    hero.addEventListener("mousemove", onMove);
    return () => hero.removeEventListener("mousemove", onMove);
  }, []);

  const handleDemo = async () => {
    const result = await signIn("credentials", {
      demo: "true",
      redirect: false,
    });
    if (!result?.error) {
      router.push("/");
      router.refresh();
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav — transparent at top, solid on scroll */}
      <nav className="fixed top-0 left-0 right-0 z-30 transition-all duration-300" id="landing-nav">
        <div className="mx-auto flex h-14 max-w-[1230px] items-center justify-between px-6" id="nav-inner">
          <div className="flex items-center gap-2.5">
            <Icon name="telescope" size={20} className="text-foreground" aria-hidden />
            <span className="font-heading text-lg">Earendel</span>
          </div>
          <div className="hidden items-center gap-6 md:flex">
            <a href="#how" className="er-caption text-muted-foreground hover:text-foreground">How it works</a>
            <a href="#features" className="er-caption text-muted-foreground hover:text-foreground">Features</a>
            <a href="#preview" className="er-caption text-muted-foreground hover:text-foreground">Live preview</a>
            <a href="#research" className="er-caption text-muted-foreground hover:text-foreground">Research</a>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" className="rounded-full" onClick={onAuth}>Sign in</Button>
            <Button size="sm" variant="outline" className="rounded-full" onClick={handleDemo}>Demo</Button>
            <Button size="sm" className="rounded-full" onClick={onSignUp}>Get started</Button>
          </div>
        </div>
      </nav>

      {/* Hero — always-animated interactive background */}
      <section ref={heroRef} className="relative overflow-hidden pt-14" style={{ "--mx": "50%", "--my": "30%" } as React.CSSProperties}>
        {/* Animated grid — slowly drifting + reacts to mouse */}
        <motion.div
          className="absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(rgba(66, 64, 61, 0.35) 1px, transparent 1px),
              linear-gradient(90deg, rgba(66, 64, 61, 0.35) 1px, transparent 1px)
            `,
            backgroundSize: "48px 48px",
            maskImage: `radial-gradient(circle 600px at var(--mx) var(--my), rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.3) 40%, transparent 70%)`,
            WebkitMaskImage: `radial-gradient(circle 600px at var(--mx) var(--my), rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.3) 40%, transparent 70%)`,
          }}
          animate={{ backgroundPositionX: ["0px", "48px"], backgroundPositionY: ["0px", "48px"] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          aria-hidden
        />

        {/* Conic gradient sweep — slow rotating light beam */}
        <motion.div
          className="absolute left-1/2 top-1/2 h-[800px] w-[800px] -translate-x-1/2 -translate-y-1/2"
          style={{
            background: `conic-gradient(from 0deg at 50% 50%,
              transparent 0deg,
              rgba(107, 88, 118, 0.08) 30deg,
              transparent 60deg,
              transparent 180deg,
              rgba(122, 133, 72, 0.06) 210deg,
              transparent 240deg,
              transparent 360deg)`,
            borderRadius: "50%",
            filter: "blur(40px)",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 40, repeat: Infinity, ease: "linear" }}
          aria-hidden
        />

        {/* Mouse-follow glow — primary purple */}
        <div
          className="absolute inset-0 transition-all duration-500 ease-out"
          style={{
            background: `radial-gradient(circle 500px at var(--mx) var(--my), rgba(107, 88, 118, 0.12) 0%, transparent 50%)`,
          }}
          aria-hidden
        />

        {/* Floating orbs — slow drift, always animating */}
        <motion.div
          className="absolute left-[8%] top-[12%] h-36 w-36 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(107,88,118,0.18) 0%, transparent 70%)" }}
          animate={{ x: [0, 40, -10, 0], y: [0, -30, 10, 0], scale: [1, 1.15, 0.95, 1] }}
          transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden
        />
        <motion.div
          className="absolute right-[12%] top-[20%] h-44 w-44 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(122,133,72,0.14) 0%, transparent 70%)" }}
          animate={{ x: [0, -35, 15, 0], y: [0, 20, -10, 0], scale: [1, 0.9, 1.1, 1] }}
          transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden
        />
        <motion.div
          className="absolute left-[55%] top-[8%] h-28 w-28 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(201,166,107,0.12) 0%, transparent 70%)" }}
          animate={{ x: [0, 25, -15, 0], y: [0, 30, 5, 0], scale: [1, 1.2, 0.9, 1] }}
          transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden
        />
        <motion.div
          className="absolute left-[25%] top-[40%] h-24 w-24 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(139,111,90,0.1) 0%, transparent 70%)" }}
          animate={{ x: [0, -20, 25, 0], y: [0, 15, -20, 0], scale: [1, 1.1, 0.85, 1] }}
          transition={{ duration: 13, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden
        />

        {/* Pulsing center glow — breathing effect */}
        <motion.div
          className="absolute left-1/2 top-[30%] h-[300px] w-[600px] -translate-x-1/2 -translate-y-1/2"
          style={{ background: "radial-gradient(ellipse at center, rgba(107,88,118,0.1) 0%, transparent 60%)" }}
          animate={{ opacity: [0.3, 0.6, 0.3], scale: [0.9, 1.05, 0.9] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          aria-hidden
        />

        {/* Subtle dot pattern overlay */}
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: `radial-gradient(circle, rgba(232,224,212,0.06) 1px, transparent 1.5px)`,
            backgroundSize: "20px 20px",
          }}
          aria-hidden
        />

        <div className="relative mx-auto max-w-[1230px]">
          {/* Hero content */}
          <div className="px-6 pt-20 pb-12 text-center">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <Badge className="er-pill-primary mb-6">
                <Icon name="sparkles" size={12} aria-hidden /> Reliability layer for agent-grade workflows
              </Badge>
              <h1 className="er-hero font-heading max-w-3xl mx-auto leading-[1.05]">
                Record workflows.{" "}
                <span className="text-accent">Compile to actions.</span>{" "}
                Let agents call them.
              </h1>
              <p className="er-body mx-auto mt-5 max-w-xl text-muted-foreground">
                Businesses still run on portals built for humans. Earendel turns
                those repeated, authorised workflows into typed, monitored, repairable
                tools your agents can call through MCP.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Button size="lg" className="rounded-full" onClick={onSignUp}>
                  <Icon name="plus" size={16} aria-hidden /> Get started free
                </Button>
                <Button size="lg" variant="outline" className="rounded-full" onClick={handleDemo}>
                  <Icon name="playground" size={16} aria-hidden /> Try the demo
                </Button>
              </div>
              <p className="er-caption mt-4 text-muted-foreground/60">
                No signup needed for demo. 6 seeded connectors ready to explore.
              </p>
            </motion.div>
          </div>

          {/* Interactive browser preview (1080px wide, centered in 1230) */}
          <motion.div
            id="preview"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="relative mx-auto px-6 pb-16"
            style={{ maxWidth: "1080px" }}
          >
            {/* Browser chrome */}
            <div className="overflow-hidden rounded-lg border border-border bg-card shadow-2xl">
              {/* Title bar */}
              <div className="flex items-center gap-2 border-b border-border bg-sidebar px-4 py-2">
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-destructive/70" aria-hidden />
                  <span className="size-2.5 rounded-full bg-chart-4/70" aria-hidden />
                  <span className="size-2.5 rounded-full bg-accent/70" aria-hidden />
                </div>
                <div className="flex flex-1 items-center justify-center">
                  <div className="flex items-center gap-1.5 rounded-md border border-border bg-background/60 px-3 py-0.5">
                    <Icon name="lock" size={10} className="text-muted-foreground" aria-hidden />
                    <span className="text-xs text-muted-foreground font-mono">earendel.io/studio</span>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Icon name="chevronLeft" size={12} className="text-muted-foreground" aria-hidden />
                  <Icon name="chevronRight" size={12} className="text-muted-foreground" aria-hidden />
                  <Icon name="sync" size={12} className="text-muted-foreground" aria-hidden />
                </div>
              </div>

              {/* The interactive studio preview */}
              <InteractiveAgentPreview />
            </div>

            {/* Caption under preview */}
            <p className="mt-3 text-center er-caption text-muted-foreground">
              This is a live interactive preview. Try the preset prompts or search actions in the sidebar.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <section className="mx-auto max-w-[1230px] px-6 py-16">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label}>
              <p className="font-heading text-3xl text-foreground">{s.value}</p>
              <p className="er-caption mt-1 text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-[1230px] px-6 py-16">
        <div className="mb-10">
          <h2 className="er-h1 font-heading">From a click to a callable tool</h2>
          <p className="er-body mt-2 max-w-2xl text-muted-foreground">
            Four steps. One recorded workflow becomes a reliable, versioned, monitored action
            your agents call through MCP.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PIPELINE.map((p) => (
            <Card key={p.title} className="p-6">
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-muted-foreground">{p.step}</span>
                <span className="grid size-8 place-items-center rounded-md bg-secondary text-muted-foreground">
                  <Icon name={p.icon} size={16} aria-hidden />
                </span>
              </div>
              <h3 className="er-h3 mt-4">{p.title}</h3>
              <p className="er-caption mt-2 text-muted-foreground leading-relaxed">{p.desc}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-[1230px] px-6 py-16">
        <div className="mb-10">
          <h2 className="er-h1 font-heading">Built for reliability, not demos</h2>
          <p className="er-body mt-2 max-w-2xl text-muted-foreground">
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
      </section>

      {/* Research */}
      <section id="research" className="mx-auto max-w-[1230px] px-6 py-16">
        <h2 className="er-h1 font-heading">Grounded in research</h2>
        <p className="er-body mt-2 max-w-2xl text-muted-foreground">
          Earendel implements the typed-actions thesis from recent systems research,
          combining program synthesis, vision-based UI parsing and traffic-based API
          discovery into one reliability discipline.
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-3">
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
      <section className="mx-auto max-w-[1230px] px-6 py-16 text-center">
        <h2 className="er-h1 font-heading">Stop clicking. Start calling.</h2>
        <p className="er-body mx-auto mt-2 max-w-xl text-muted-foreground">
          Record your first workflow in under five minutes. Compile it to a typed action.
          Publish it as an MCP tool. Let your agents call it reliably.
        </p>
        <Button size="lg" className="mt-6 rounded-full" onClick={onSignUp}>
          <Icon name="telescope" size={16} aria-hidden /> Get started free
        </Button>
      </section>

      {/* Footer */}
      <footer className="mx-auto max-w-[1230px] px-6 py-8">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-2">
            <Icon name="telescope" size={14} className="text-foreground" aria-hidden />
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
