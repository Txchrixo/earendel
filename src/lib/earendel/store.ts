"use client";

import { create } from "zustand";
import type { StudioView } from "./types";

interface StudioState {
  view: StudioView;
  selectedActionId: string | null;
  selectedConnectorId: string | null;
  selectedExecutionId: string | null;
  setView: (v: StudioView) => void;
  openAction: (id: string) => void;
  openConnector: (id: string) => void;
  openExecution: (id: string) => void;
}

export const useStudio = create<StudioState>((set) => ({
  view: "dashboard",
  selectedActionId: null,
  selectedConnectorId: null,
  selectedExecutionId: null,
  setView: (view) => set({ view }),
  openAction: (id) => set({ view: "action-detail", selectedActionId: id }),
  openConnector: (id) => set({ view: "connectors", selectedConnectorId: id }),
  openExecution: (id) => set({ view: "executions", selectedExecutionId: id }),
}));
