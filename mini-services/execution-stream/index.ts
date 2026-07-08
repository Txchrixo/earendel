/**
 * Earendel Execution Stream — WebSocket mini-service.
 *
 * Streams execution traces in real-time to connected clients via socket.io.
 * The FastAPI orchestrator pushes events via HTTP POST to this service,
 * which broadcasts them to all subscribed clients.
 *
 * Port: 3003
 * Path: / (required by Caddy gateway)
 *
 * Protocol:
 *   Client → Server: join execution room (subscribe to a specific execution)
 *   Server → Client: trace events (execution.started, trace.appended, execution.completed)
 *   FastAPI → Server: HTTP POST /emit (internal, from orchestrator)
 */
import { createServer } from "http";
import { Server } from "socket.io";

const PORT = 3003;

const httpServer = createServer();
const io = new Server(httpServer, {
  path: "/",
  cors: {
    origin: ["http://localhost:3000", "http://localhost:81", "http://127.0.0.1:3000", "http://127.0.0.1:81"],
    methods: ["GET", "POST"],
  },
  pingTimeout: 60000,
  pingInterval: 25000,
});

// Store active execution streams.
const activeStreams = new Map(); // executionId → Set<socket>

// ---- Socket.io connection handler ----

io.on("connection", (socket) => {
  console.log(`[stream] Client connected: ${socket.id}`);

  // Client subscribes to a specific execution.
  socket.on("subscribe", (executionId: string) => {
    socket.join(`exec:${executionId}`);
    console.log(`[stream] ${socket.id} subscribed to execution ${executionId}`);

    if (!activeStreams.has(executionId)) {
      activeStreams.set(executionId, new Set());
    }
    activeStreams.get(executionId).add(socket);
  });

  // Client unsubscribes.
  socket.on("unsubscribe", (executionId: string) => {
    socket.leave(`exec:${executionId}`);
    const set = activeStreams.get(executionId);
    if (set) {
      set.delete(socket);
      if (set.size === 0) activeStreams.delete(executionId);
    }
  });

  socket.on("disconnect", () => {
    console.log(`[stream] Client disconnected: ${socket.id}`);
    // Clean up subscriptions.
    for (const [execId, sockets] of activeStreams) {
      sockets.delete(socket);
      if (sockets.size === 0) activeStreams.delete(execId);
    }
  });
});

// ---- HTTP endpoint for FastAPI orchestrator to push events ----

httpServer.on("request", (req, res) => {
  if (req.method === "POST" && req.url === "/emit") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      try {
        const data = JSON.parse(body);
        const { executionId, event, payload } = data;

        if (!executionId || !event) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Missing executionId or event" }));
          return;
        }

        // Broadcast to all clients subscribed to this execution.
        io.to(`exec:${executionId}`).emit(event, payload);
        console.log(`[stream] Emitted ${event} to exec:${executionId} (${io.sockets.adapter.rooms.get(`exec:${executionId}`)?.size || 0} clients)`);

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      } catch (err) {
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: "ok",
      service: "earendel-execution-stream",
      port: PORT,
      activeStreams: activeStreams.size,
      connectedClients: io.engine.clientsCount,
    }));
    return;
  }

  res.writeHead(404);
  res.end("Not found");
});

httpServer.listen(PORT, () => {
  console.log(`Earendel Execution Stream running on port ${PORT}`);
  console.log(`  WebSocket: ws://localhost:${PORT}/`);
  console.log(`  Health:    GET http://localhost:${PORT}/health`);
  console.log(`  Emit:      POST http://localhost:${PORT}/emit`);
});

// Graceful shutdown.
process.on("SIGTERM", () => {
  console.log("[stream] Shutting down...");
  io.close(() => httpServer.close(() => process.exit(0)));
});
process.on("SIGINT", () => {
  console.log("[stream] Shutting down...");
  io.close(() => httpServer.close(() => process.exit(0)));
});
