"""In-memory log aggregation for the supervisor.

Keeps a bounded ring buffer of recent lines per component and supports async
fan-out to subscribers (the ``WS /events`` stream). The supervisor logs its own
*observations* (process stdout, health transitions); kernel-internal MCP logs live
out of process and are not captured here.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Optional


class LogStore:
    """Bounded per-component log buffers with async pub/sub."""

    def __init__(self, maxlen: int = 2000) -> None:
        self._maxlen = maxlen
        self._buffers: dict[str, deque] = {}
        self._subscribers: set[asyncio.Queue] = set()

    # -- writing ----------------------------------------------------------

    def append(self, component: str, line: str) -> None:
        """Append a log line for ``component`` and notify subscribers."""
        line = line.rstrip("\n")
        buf = self._buffers.get(component)
        if buf is None:
            buf = deque(maxlen=self._maxlen)
            self._buffers[component] = buf
        record = {"component": component, "line": line, "ts": time.time()}
        buf.append(record)
        self._publish({"type": "log", **record})

    # -- reading ----------------------------------------------------------

    def tail(self, component: Optional[str] = None, lines: int = 200) -> list[dict]:
        """Return the most recent ``lines`` records, optionally filtered by component."""
        if component is not None:
            buf = self._buffers.get(component)
            records = list(buf)[-lines:] if buf else []
            return records
        # Merge all components, sort by timestamp, take the tail.
        merged: list[dict] = []
        for buf in self._buffers.values():
            merged.extend(buf)
        merged.sort(key=lambda r: r["ts"])
        return merged[-lines:]

    def components(self) -> list[str]:
        """Return the names of components that have logged anything."""
        return sorted(self._buffers)

    # -- pub/sub ----------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """Register a subscriber queue for live events (logs + broadcasts)."""
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def broadcast(self, event: dict) -> None:
        """Publish an arbitrary event (e.g. a status change) to all subscribers."""
        self._publish(event)

    def _publish(self, event: dict) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer: drop the oldest, then enqueue the newest.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass
