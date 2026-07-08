"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Icon } from "../icon";
import { useApi } from "../use-api";
import { api } from "@/lib/earendel/api-client";
import { SectionTitle, EmptyState } from "../primitives";
import type { Connector } from "@/lib/earendel/types";
import { ConnectorCard, NewConnectorDialog } from "./connectors-sections";

/**
 * ConnectorsView — the "Create connector" step of the user journey.
 *
 * Lists authorised bridges to portals/apps with risk, permission, allowed
 * domains, vault key, status. A "New connector" dialog creates one via the
 * FastAPI backend. Each card expands to reveal workflow details + a
 * "Record workflow" shortcut into the Recorder view.
 */
export function ConnectorsView() {
  const { data, loading, error, refetch } = useApi<Connector[]>(
    () => api.listConnectors(),
    [],
  );
  const connectors = data ?? [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8"
    >
      <SectionTitle
        icon="connectors"
        title="Connectors"
        subtitle="Authorized bridges to the portals and apps your teams already use."
        action={<NewConnectorDialog onCreated={refetch} />}
      />

      {error ? (
        <EmptyState
          icon="connectors"
          spot="connectors"
          title="Backend connecting…"
          description="Your connectors will appear here once the FastAPI service is reachable."
          action={
            <Button variant="outline" size="sm" className="rounded-full" onClick={refetch}>
              <Icon name="sync" size={14} aria-hidden /> Retry
            </Button>
          }
        />
      ) : loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="gap-3 p-4">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-4 w-full" />
            </Card>
          ))}
        </div>
      ) : connectors.length === 0 ? (
        <EmptyState
          icon="connectors"
          spot="connectors"
          title="No connectors yet"
          description="Authorize your first portal or app to start recording workflows."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {connectors.map((c) => (
            <ConnectorCard key={c.id} connector={c} />
          ))}
        </div>
      )}
    </motion.div>
  );
}

export default ConnectorsView;
