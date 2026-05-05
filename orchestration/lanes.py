from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class LanePriority(IntEnum):
    """Lane priority (lower = higher priority)."""
    MAIN = 0       # User messages — highest priority
    CRON = 10      # Scheduled tasks
    HEARTBEAT = 20 # Heartbeat checks — lowest priority


@dataclass
class Lane:
    """A named lane with a priority and message queue."""
    name: str
    priority: LanePriority
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    async def put(self, item: Any) -> None:
        await self._queue.put(item)

    def put_nowait(self, item: Any) -> None:
        self._queue.put_nowait(item)

    async def get(self) -> Any:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()


class LaneQueue:
    """
    Named lane queue system with priority-based consumption.
    Higher priority lanes are drained first.
    """

    def __init__(self) -> None:
        self._lanes: dict[str, Lane] = {}

    def register(self, name: str, priority: LanePriority) -> Lane:
        """Register a new lane."""
        lane = Lane(name=name, priority=priority)
        self._lanes[name] = lane
        return lane

    def get_lane(self, name: str) -> Lane | None:
        """Get a lane by name."""
        return self._lanes.get(name)

    async def consume(self) -> tuple[str, Any]:
        """
        Consume the next item from the highest-priority non-empty lane.
        Blocks until an item is available.
        """
        while True:
            # Sort lanes by priority
            sorted_lanes = sorted(self._lanes.values(), key=lambda l: l.priority)
            for lane in sorted_lanes:
                if not lane.empty():
                    item = await lane.get()
                    return lane.name, item
            # No items available — wait briefly and retry
            await asyncio.sleep(0.01)

    def sizes(self) -> dict[str, int]:
        """Return queue sizes for all lanes."""
        return {name: lane.qsize() for name, lane in self._lanes.items()}

    @property
    def lanes(self) -> dict[str, Lane]:
        return dict(self._lanes)
