from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class HeartbeatService:
    """
    Periodic heartbeat check: determines if the agent needs to proactively speak.
    Runs on a configurable interval, calling a check function.
    Also triggers delivery queue retry on each cycle.
    """

    def __init__(
        self,
        interval_seconds: float = 60.0,
        check_fn: Callable[[], Awaitable[bool]] | None = None,
        on_heartbeat: Callable[[], Awaitable[None]] | None = None,
        delivery_queue: object | None = None,
    ) -> None:
        self._interval = interval_seconds
        self._check_fn = check_fn
        self._on_heartbeat = on_heartbeat
        self._delivery_queue = delivery_queue
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the heartbeat loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat started (interval={self._interval}s)")

    async def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                # Retry pending deliveries on every heartbeat
                if self._delivery_queue and hasattr(self._delivery_queue, 'retry_pending'):
                    try:
                        retried = await self._delivery_queue.retry_pending()
                        if retried:
                            logger.info(f"Heartbeat: retried {retried} pending deliveries")
                    except Exception as e:
                        logger.warning(f"Heartbeat delivery retry failed: {e}")

                should_act = True
                if self._check_fn:
                    should_act = await self._check_fn()

                if should_act and self._on_heartbeat:
                    await self._on_heartbeat()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            await asyncio.sleep(self._interval)

    @property
    def is_running(self) -> bool:
        return self._running
