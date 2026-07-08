"use client";

import * as React from "react";
import { AppShell } from "@/components/earendel/app-shell";
import { LandingPage } from "@/components/earendel/landing-page";
import { AuthDialog } from "@/components/earendel/auth-dialog";
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
    case "publishing":
      return <PublishingView />;
    case "playground":
      return <PlaygroundView />;
    default:
      return <DashboardView />;
  }
}

export default function Home() {
  const entered = useStudio((s) => s.entered);
  const setEntered = useStudio((s) => s.setEntered);

  if (!entered) {
    return (
      <>
        <LandingPage
          onEnter={() => setEntered(true)}
          onAuth={() => useStudio.getState().setAuthOpen(true)}
        />
        <AuthDialog />
      </>
    );
  }

  return (
    <AppShell>
      <CurrentView />
    </AppShell>
  );
}
