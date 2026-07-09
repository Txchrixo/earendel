"""Telemetry — in-memory trace collector used by adapters + orchestrator."""
from __future__ import annotations

from collections import deque
from datetime import datetime

from ..core.domain.entities import TraceEvent


class TraceCollector:
    """Per-run buffer of TraceEvent; flushed by the orchestrator at the end."""

    def __init__(self, capacity: int = 512) -> None:
        self._events: deque[TraceEvent] = deque(maxlen=capacity)

    def add(self, event: TraceEvent) -> None:
        """Append a trace event."""
        self._events.append(event)

    def flush(self) -> list[TraceEvent]:
        """Drain the buffer and return the events in insertion order."""
        out = list(self._events)
        self._events.clear()
        return out

    def now(self) -> datetime:
        """Stable time source (mockable)."""
        return datetime.utcnow()
