"use client";

import { useEffect, useRef } from "react";
import { io, Socket } from "socket.io-client";
import type { TraceEvent } from "@/lib/earendel/types";

/**
 * useExecutionStream — subscribe to real-time execution events.
 *
 * Connects to the execution-stream mini-service (port 3003) via socket.io.
 * The frontend connects via io("/?XTransformPort=3003") through the Caddy
 * gateway so the URL stays relative.
 *
 * Returns a ref to the socket for manual subscribe/unsubscribe.
 */
export function useExecutionStream(executionId: string | null) {
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    if (!executionId) return;

    const socket = io("/?XTransformPort=3003", {
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socketRef.current = socket;

    socket.on("connect", () => {
      socket.emit("subscribe", executionId);
    });

    socket.on("disconnect", () => {
      // Will auto-reconnect.
    });

    return () => {
      socket.emit("unsubscribe", executionId);
      socket.disconnect();
      socketRef.current = null;
    };
  }, [executionId]);

  return socketRef;
}

/**
 * Subscribe to execution events with callbacks.
 */
export function useExecutionEvents(
  executionId: string | null,
  callbacks: {
    onStarted?: (payload: unknown) => void;
    onTrace?: (trace: Partial<TraceEvent>) => void;
    onCompleted?: (payload: unknown) => void;
  },
) {
  const socketRef = useExecutionStream(executionId);

  useEffect(() => {
    const socket = socketRef.current;
    if (!socket) return;

    if (callbacks.onStarted) {
      socket.on("execution.started", callbacks.onStarted);
    }
    if (callbacks.onTrace) {
      socket.on("trace.appended", callbacks.onTrace);
    }
    if (callbacks.onCompleted) {
      socket.on("execution.completed", callbacks.onCompleted);
    }

    return () => {
      if (callbacks.onStarted) socket.off("execution.started");
      if (callbacks.onTrace) socket.off("trace.appended");
      if (callbacks.onCompleted) socket.off("execution.completed");
    };
  }, [socketRef, callbacks]);
}
