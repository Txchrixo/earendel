"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Icon, type ErIconName } from "./icon";
import { useStudio } from "@/lib/earendel/store";
import type { StudioView } from "@/lib/earendel/types";
import { Toaster as SonnerToaster } from "@/components/ui/sonner";

interface NavItem {
  id: StudioView;
  label: string;
  icon: ErIconName;
  hint: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard", hint: "Overview" },
  { id: "connectors", label: "Connectors", icon: "connectors", hint: "Authorised apps" },
  { id: "recorder", label: "Recorder", icon: "recorder", hint: "Capture a workflow" },
  { id: "actions", label: "Actions", icon: "actions", hint: "Typed action catalog" },
  { id: "executions", label: "Executions", icon: "executions", hint: "Live + historical runs" },
  { id: "monitoring", label: "Monitoring", icon: "monitoring", hint: "Canaries & repairs" },
  { id: "publishing", label: "Publishing", icon: "publishing", hint: "MCP / REST / SDK" },
  { id: "playground", label: "Playground", icon: "playground", hint: "Call actions as an agent" },
];

const VIEW_META: Record<StudioView, { title: string; subtitle: string }> = {
  dashboard: { title: "Dashboard", subtitle: "Earendel at a glance" },
  connectors: { title: "Connectors", subtitle: "Authorised business apps" },
  "connector-detail": { title: "Connector", subtitle: "Bridge details, actions and recent runs" },
  recorder: { title: "Recorder", subtitle: "Capture a human workflow" },
  actions: { title: "Actions", subtitle: "Typed action catalog" },
  "action-detail": { title: "Action detail", subtitle: "Contract, tests, versions, runs" },
  executions: { title: "Executions", subtitle: "Live and historical runs" },
  monitoring: { title: "Monitoring", subtitle: "Canaries, repairs, reliability" },
  publishing: { title: "Publishing", subtitle: "MCP, REST, SDK, webhooks" },
  playground: { title: "Playground", subtitle: "Invoke actions as an agent" },
};

const VERSION = "0.1.0";

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5 px-2 py-1">
      <span
        className="grid size-9 place-items-center rounded-md"
        style={{
          background:
            "linear-gradient(135deg, #6B5876 0%, #7A8548 100%)",
          color: "#1F1A17",
          boxShadow:
            "inset 0 1px 0 0 rgba(232,224,212,0.25), 0 6px 16px -8px rgba(122,133,72,0.6)",
        }}
      >
        <Icon name="telescope" size={20} aria-hidden />
      </span>
      <div className="leading-tight">
        <p className="font-heading text-xl tracking-tight">Earendel</p>
        <p className="er-caption text-muted-foreground">Studio</p>
      </div>
    </div>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const view = useStudio((s) => s.view);
  const setView = useStudio((s) => s.setView);
  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5 px-2">
      {NAV_ITEMS.map((item) => {
        const active = view === item.id || (item.id === "actions" && view === "action-detail");
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setView(item.id);
              onNavigate?.();
            }}
            aria-current={active ? "page" : undefined}
            className={cn(
              "er-lift group relative flex items-center gap-3 rounded-md px-3 py-2 text-left text-sm",
              active
                ? "er-nav-active text-foreground"
                : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
            )}
          >
            <Icon
              name={item.icon}
              size={16}
              aria-hidden
              className={active ? "text-accent" : "text-muted-foreground group-hover:text-foreground"}
            />
            <span className="flex flex-col">
              <span className={active ? "font-medium" : ""}>{item.label}</span>
              <span className="er-caption text-muted-foreground">{item.hint}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-4 py-4">
      <Wordmark />
      <div className="mx-2 h-px bg-border" />
      <div className="flex-1 overflow-y-auto er-scroll">
        <NavList onNavigate={onNavigate} />
      </div>
      <div className="mx-3 rounded-md border border-border bg-card/40 p-3">
        <div className="flex items-center justify-between">
          <p className="er-caption flex items-center gap-1.5 text-muted-foreground">
            <Icon name="sparkles" size={12} aria-hidden /> v{VERSION}
          </p>
          <span className="inline-flex items-center gap-1.5 er-pill-success px-2 py-0.5 er-caption rounded-full">
            <span className="size-1.5 rounded-full bg-accent er-pulse" aria-hidden />
            Live
          </span>
        </div>
        <p className="er-caption mt-2 text-muted-foreground">
          All systems nominal. Canary pass rate 100%.
        </p>
      </div>
    </div>
  );
}

function Header() {
  const view = useStudio((s) => s.view);
  const setView = useStudio((s) => s.setView);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const meta = VIEW_META[view] ?? VIEW_META.dashboard;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
      {/* Mobile drawer trigger */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open navigation menu"
          >
            <Icon name="workflow" size={20} aria-hidden />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 border-r border-border bg-sidebar p-0">
          <SheetTitle className="sr-only">Earendel navigation</SheetTitle>
          <SidebarBody onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="min-w-0 flex-1">
        <h1 className="font-heading text-xl leading-tight">{meta.title}</h1>
        <p className="er-caption text-muted-foreground">{meta.subtitle}</p>
      </div>

      <div className="hidden flex-1 max-w-md items-center gap-2 lg:flex">
        <div className="relative w-full">
          <Icon
            name="search"
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            placeholder="Search actions, connectors, executions…"
            aria-label="Search"
            className="pl-9"
          />
        </div>
      </div>

      <Button onClick={() => setView("connectors")} className="hidden sm:inline-flex">
        <Icon name="plus" size={16} aria-hidden /> New connector
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Notifications"
        className="relative"
      >
        <Icon name="bell" size={18} aria-hidden />
        <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-accent" aria-hidden />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Account"
        className="rounded-full bg-secondary"
      >
        <Icon name="person" size={18} aria-hidden />
      </Button>
    </header>
  );
}

function Footer() {
  return (
    <footer className="mt-auto border-t border-border bg-background/80 px-6 py-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <Icon name="telescope" size={14} className="text-accent" aria-hidden />
          <p className="er-caption text-muted-foreground">
            A reliability layer for agent-grade business workflows.
          </p>
        </div>
        <div className="flex items-center gap-4 er-caption text-muted-foreground">
          <a className="hover:text-foreground" href="#">Docs</a>
          <span aria-hidden>·</span>
          <a className="hover:text-foreground" href="#">MCP registry</a>
          <span aria-hidden>·</span>
          <a className="hover:text-foreground" href="#">Status</a>
          <span aria-hidden>·</span>
          <span>v{VERSION}</span>
        </div>
      </div>
    </footer>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <div className="flex flex-1 overflow-hidden">
        <aside className="hidden w-64 shrink-0 border-r border-border bg-sidebar md:block">
          <SidebarBody />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="flex-1 overflow-y-auto er-scroll">{children}</main>
        </div>
      </div>
      <Footer />
      <SonnerToaster richColors closeButton position="bottom-right" />
    </div>
  );
}

export default AppShell;
