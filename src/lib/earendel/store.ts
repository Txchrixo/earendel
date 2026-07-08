"use client";

import { create } from "zustand";
import type { StudioView } from "./types";

interface StudioState {
  entered: boolean;
  authOpen: boolean;
  user: { email: string; name: string } | null;
  view: StudioView;
  selectedActionId: string | null;
  selectedConnectorId: string | null;
  selectedExecutionId: string | null;
  selectedRecordingId: string | null;
  setEntered: (v: boolean) => void;
  setAuthOpen: (v: boolean) => void;
  setUser: (u: { email: string; name: string } | null) => void;
  setView: (v: StudioView) => void;
  openAction: (id: string) => void;
  openConnector: (id: string) => void;
  openExecution: (id: string) => void;
  openRecording: (id: string) => void;
}

export const useStudio = create<StudioState>((set) => ({
  entered: false,
  authOpen: false,
  user: null,
  view: "dashboard",
  selectedActionId: null,
  selectedConnectorId: null,
  selectedExecutionId: null,
  selectedRecordingId: null,
  setEntered: (entered) => set({ entered }),
  setAuthOpen: (authOpen) => set({ authOpen }),
  setUser: (user) => set({ user }),
  setView: (view) => set({ view }),
  openAction: (id) => set({ view: "action-detail", selectedActionId: id }),
  openConnector: (id) => set({ view: "connector-detail", selectedConnectorId: id }),
  openExecution: (id) => set({ view: "executions", selectedExecutionId: id }),
  openRecording: (id) => set({ view: "recording-detail", selectedRecordingId: id }),
}));
