"use client";

import { motion } from "framer-motion";
import {
  Hero,
  StatsSection,
  PipelineSection,
  ReliabilitySection,
  RecentExecutionsSection,
  OpenRepairsSection,
} from "./dashboard-sections";

/**
 * DashboardView — the Earendel landing view.
 *
 * Composes the hero, stat row, pipeline diagram, reliability summary,
 * recent executions and open repair proposals. Each section fetches its
 * own data via the shared `useApi` hook and degrades gracefully when the
 * FastAPI backend is unreachable (skeletons + muted "backend connecting…"
 * notes, never a crash).
 */
export function DashboardView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-8 p-6 md:p-8"
    >
      <Hero />
      <StatsSection />
      <PipelineSection />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <ReliabilitySection />
        <RecentExecutionsSection />
      </div>
      <OpenRepairsSection />
    </motion.div>
  );
}

export default DashboardView;
