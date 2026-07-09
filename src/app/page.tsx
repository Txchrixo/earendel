"use client";

import { useSession } from "next-auth/react";
import { AppShell } from "@/components/earendel/app-shell";
import { LandingPage } from "@/components/earendel/landing-page";
import { useStudio } from "@/lib/earendel/store";
import { DashboardView } from "@/components/earendel/views/dashboard-view";
import { ConnectorsView } from "@/components/earendel/views/connectors-view";
import { ConnectorDetailView } from "@/components/earendel/views/connector-detail-view";
import { RecorderView } from "@/components/earendel/views/recorder-view";
import { RecordingDetailView } from "@/components/earendel/views/recording-detail-view";
import { ActionsView } from "@/components/earendel/views/actions-view";
import { ActionDetailView } from "@/components/earendel/views/action-detail-view";
import { ExecutionsView } from "@/components/earendel/views/executions-view";
import { MonitoringView } from "@/components/earendel/views/monitoring-view";
import { DiscoveryView } from "@/components/earendel/views/discovery-view";
import { RepairKBView } from "@/components/earendel/views/repair-kb-view";
import { PublishingView } from "@/components/earendel/views/publishing-view";
import { PlaygroundView } from "@/components/earendel/views/playground-view";

function CurrentView() {
  const view = useStudio((s) => s.view);
  switch (view) {
    case "dashboard":
      return <DashboardView />;
    case "connectors":
      return <ConnectorsView />;
    case "connector-detail":
      return <ConnectorDetailView />;
    case "recorder":
      return <RecorderView />;
    case "recording-detail":
      return <RecordingDetailView />;
    case "actions":
      return <ActionsView />;
    case "action-detail":
      return <ActionDetailView />;
    case "executions":
      return <ExecutionsView />;
    case "monitoring":
      return <MonitoringView />;
    case "discovery":
      return <DiscoveryView />;
    case "repair_kb":
      return <RepairKBView />;
    case "publishing":
      return <PublishingView />;
    case "playground":
      return <PlaygroundView />;
    default:
      return <DashboardView />;
  }
}

export default function Home() {
  const { data: session, status } = useSession();
  const setEntered = useStudio((s) => s.setEntered);

  // Sync entered state with session
  const isAuthenticated = status === "authenticated" && !!session;

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="er-pulse text-muted-foreground">Loading…</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <LandingPage
        onEnter={() => setEntered(true)}
        onAuth={() => (window.location.href = "/auth/signin")}
        onSignUp={() => (window.location.href = "/auth/signup")}
      />
    );
  }

  return (
    <AppShell>
      <CurrentView />
    </AppShell>
  );
}
