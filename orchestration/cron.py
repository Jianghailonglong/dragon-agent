from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class CronJob:
    """A scheduled recurring job."""
    name: str
    interval_seconds: float
    callback: Callable[[], Awaitable[None]]
    enabled: bool = True
    last_run: datetime | None = None
    run_count: int = 0

    def should_run(self, now: datetime) -> bool:
        """Check if this job should run now."""
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        return (now - self.last_run).total_seconds() >= self.interval_seconds

    def mark_ran(self) -> None:
        self.last_run = datetime.now()
        self.run_count += 1


class CronScheduler:
    """
    Simple cron-like scheduler for periodic tasks.
    Jobs are checked every second and run when their interval elapses.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def add_job(self, name: str, interval_seconds: float, callback: Callable[[], Awaitable[None]]) -> CronJob:
        """Register a new cron job."""
        job = CronJob(name=name, interval_seconds=interval_seconds, callback=callback)
        self._jobs[name] = job
        return job

    def remove_job(self, name: str) -> None:
        """Remove a cron job."""
        self._jobs.pop(name, None)

    def enable_job(self, name: str) -> None:
        job = self._jobs.get(name)
        if job:
            job.enabled = True

    def disable_job(self, name: str) -> None:
        job = self._jobs.get(name)
        if job:
            job.enabled = False

    def get_job(self, name: str) -> CronJob | None:
        return self._jobs.get(name)

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("CronScheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("CronScheduler stopped")

    async def run_once(self, name: str) -> None:
        """Manually trigger a job once."""
        job = self._jobs.get(name)
        if job:
            await job.callback()
            job.mark_ran()

    async def _loop(self) -> None:
        while self._running:
            now = datetime.now()
            for job in self._jobs.values():
                if job.should_run(now):
                    try:
                        await job.callback()
                        job.mark_ran()
                    except asyncio.CancelledError:
                        return
                    except Exception as e:
                        logger.error(f"Cron job '{job.name}' failed: {e}")
            await asyncio.sleep(0.5)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def jobs(self) -> dict[str, CronJob]:
        return dict(self._jobs)
