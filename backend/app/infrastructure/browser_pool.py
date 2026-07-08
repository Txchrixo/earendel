"""Browser pool — stub that leases fake Playwright context handles."""
from __future__ import annotations

import uuid
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator


class BrowserPool:
    """Pretends to lease Playwright browser contexts (no real chromium)."""

    def __init__(self, size: int = 4) -> None:
        self._free: deque[str] = deque(
            f"ctx-{i}-{uuid.uuid4().hex[:6]}" for i in range(size)
        )

    async def acquire(self) -> str:
        """Lease a context handle, blocking-free in this stub."""
        if not self._free:
            self._free.append(f"ctx-x-{uuid.uuid4().hex[:6]}")
        return self._free.popleft()

    async def release(self, handle: str) -> None:
        """Return a context handle to the pool."""
        self._free.append(handle)

    @asynccontextmanager
    async def lease(self) -> AsyncIterator[str]:
        """Async context manager yielding a leased handle."""
        handle = await self.acquire()
        try:
            yield handle
        finally:
            await self.release(handle)
