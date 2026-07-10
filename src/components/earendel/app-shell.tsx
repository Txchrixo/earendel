"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { GlobalSearch } from "./global-search";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon, type ErIconName } from "./icon";
import { useStudio } from "@/lib/earendel/store";
import type { StudioView } from "@/lib/earendel/types";
import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useSession } from "next-auth/react";

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
  { id: "discovery", label: "Discovery", icon: "globe", hint: "HAR → internal routes" },
  { id: "repair_kb", label: "Repair KB", icon: "database", hint: "Cross-client repair flywheel" },
  { id: "publishing", label: "Publishing", icon: "publishing", hint: "MCP / REST / SDK" },
  { id: "playground", label: "Playground", icon: "playground", hint: "Call actions as an agent" },
];

const VIEW_META: Record<StudioView, { title: string; subtitle: string }> = {
  dashboard: { title: "Dashboard", subtitle: "Earendel at a glance" },
  connectors: { title: "Connectors", subtitle: "Authorised business apps" },
  "connector-detail": { title: "Connector", subtitle: "Bridge details, actions and recent runs" },
  recorder: { title: "Recorder", subtitle: "Capture a human workflow" },
  "recording-detail": { title: "Recording", subtitle: "Captured workflow steps and compile status" },
  actions: { title: "Actions", subtitle: "Typed action catalog" },
  "action-detail": { title: "Action detail", subtitle: "Contract, tests, versions, runs" },
  executions: { title: "Executions", subtitle: "Live and historical runs" },
  monitoring: { title: "Monitoring", subtitle: "Canaries, repairs, reliability" },
  discovery: { title: "Network Discovery", subtitle: "Internal endpoints learned from HAR captures" },
  repair_kb: { title: "Repair Knowledge Base", subtitle: "Cross-client repair flywheel" },
  publishing: { title: "Publishing", subtitle: "MCP, REST, SDK, webhooks" },
  playground: { title: "Playground", subtitle: "Invoke actions as an agent" },
};

const VERSION = "0.1.0";

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5 px-2 py-1">
      <span className="grid size-9 place-items-center rounded-md bg-primary text-primary-foreground">
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
              "flex items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
              active
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
            )}
          >
            <Icon
              name={item.icon}
              size={16}
              aria-hidden
              className={active ? "text-accent" : "text-muted-foreground"}
            />
            <span className="flex flex-col">
              <span className={active ? "font-medium" : ""}>{item.label}</span>
              <span className="er-caption text-muted-foreground hidden sm:flex">{item.hint}</span>
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
      <div className="mx-3 rounded-md border border-border bg-card/50 p-3">
        <div className="flex items-center justify-between">
          <p className="er-caption text-muted-foreground">v{VERSION}</p>
          <span className="inline-flex items-center gap-1.5 er-pill-success px-2 py-0.5 er-caption rounded-full">
            <span className="size-1.5 rounded-full bg-accent er-pulse" aria-hidden />
            Live
          </span>
        </div>
      </div>
    </div>
  );
}

function Header() {
  const view = useStudio((s) => s.view);
  const setView = useStudio((s) => s.setView);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const meta = VIEW_META[view] ?? VIEW_META.dashboard;
  // Use the real NextAuth session email when available; fall back to the
  // demo address so the dropdown still has a label in unauthenticated mode.
  const { data: session } = useSession();
  const accountLabel = session?.user?.email || "demo@earendel.io";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background px-4">
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
        <h1 className="font-heading text-xl leading-tight truncate">{meta.title}</h1>
        <p className="er-caption text-muted-foreground truncate">{meta.subtitle}</p>
      </div>

      <div className="hidden flex-1 max-w-md items-center gap-2 lg:flex">
        <GlobalSearch />
      </div>

      <Button onClick={() => setView("connectors")} className="hidden sm:inline-flex shrink-0 rounded-full">
        <Icon name="plus" size={16} aria-hidden /> New
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Notifications"
            className="relative shrink-0"
          >
            <Icon name="bell" size={18} aria-hidden />
            <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-accent" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel>Notifications</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => { setView("monitoring"); toast.info("Opening monitoring view"); }}>
            <Icon name="bell" size={14} aria-hidden /> Recent repair proposals
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => { setView("executions"); toast.info("Opening executions view"); }}>
            <Icon name="executions" size={14} aria-hidden /> Recent execution results
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => { setView("discovery"); toast.info("Opening discovery view"); }}>
            <Icon name="globe" size={14} aria-hidden /> Stale endpoints
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => toast.success("All caught up! No new notifications.")}>
            <Icon name="check" size={14} aria-hidden /> Mark all as read
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Account"
            className="rounded-full bg-secondary shrink-0"
          >
            <Icon name="person" size={18} aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>{accountLabel}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => { setView("dashboard"); toast.info("Opening dashboard"); }}>
            <Icon name="dashboard" size={14} aria-hidden /> Dashboard
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => { setView("publishing"); toast.info("Opening publishing view"); }}>
            <Icon name="publishing" size={14} aria-hidden /> MCP Settings
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => toast.info("API key: check the Publishing view for MCP config")}>
            <Icon name="key" size={14} aria-hidden /> API Key
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => { window.location.href = "/auth/signout"; }}>
            <Icon name="signOut" size={14} aria-hidden /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}

function Footer() {
  return (
    <footer className="mt-auto border-t border-border bg-background px-4 py-4 md:px-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <Icon name="telescope" size={14} className="text-accent" aria-hidden />
          <p className="er-caption text-muted-foreground">
            A reliability layer for agent-grade business workflows.
          </p>
        </div>
        <div className="flex items-center gap-4 er-caption text-muted-foreground">
          <a className="hover:text-foreground transition-colors" href="/api/v1/readyz" target="_blank" rel="noopener noreferrer">Docs</a>
          <span aria-hidden>·</span>
          <a className="hover:text-foreground transition-colors" href="#" onClick={(e) => { e.preventDefault(); useStudio.getState().setView("publishing"); }}>MCP registry</a>
          <span aria-hidden>·</span>
          <a className="hover:text-foreground transition-colors" href="/api/v1/healthz" target="_blank" rel="noopener noreferrer">Status</a>
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
