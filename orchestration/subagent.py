from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable

from providers.base import LLMProvider
from tools.registry import ToolRegistry
from core.runner import AgentRunner, AgentRunSpec, AgentRunResult
from core.hook import AgentHook

logger = logging.getLogger(__name__)


@dataclass
class SubagentTask:
    """A spawned subagent task."""
    id: str
    task_description: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    result: AgentRunResult | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error: str = ""
    event: asyncio.Event = field(default_factory=asyncio.Event)


class SubagentManager:
    """
    Manages subagent spawning for parallel task execution.
    Subagents share the same provider and tools but run independently.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        max_concurrent: int = 3,
        max_iterations: int = 10,
        system_prompt: str = "",
    ) -> None:
        self._provider = provider
        self._tools = tools
        self._max_concurrent = max_concurrent
        self._max_iterations = max_iterations
        self._system_prompt = system_prompt
        self._runner = AgentRunner()
        self._tasks: dict[str, SubagentTask] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def spawn(self, task_description: str, parent_context: str = "") -> str:
        """
        Spawn a subagent to handle a task.
        Returns the task ID immediately (non-blocking).
        """
        task_id = f"sub_{uuid.uuid4().hex[:8]}"
        task = SubagentTask(id=task_id, task_description=task_description)
        self._tasks[task_id] = task

        # Launch in background
        asyncio.create_task(self._run_subagent(task, parent_context))
        return task_id

    async def spawn_and_wait(self, task_description: str, parent_context: str = "") -> AgentRunResult:
        """Spawn a subagent and wait for its result."""
        task_id = await self.spawn(task_description, parent_context)
        return await self.wait(task_id)

    async def wait(self, task_id: str) -> AgentRunResult:
        """Wait for a subagent task to complete using asyncio.Event."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        await task.event.wait()

        if task.status == "failed":
            raise RuntimeError(f"Subagent task failed: {task.error}")
        if task.result is None:
            raise RuntimeError("Subagent completed but produced no result")
        return task.result

    async def _run_subagent(self, task: SubagentTask, parent_context: str) -> None:
        async with self._semaphore:
            task.status = "running"
            try:
                messages = []
                if parent_context:
                    messages.append({"role": "user", "content": f"Context from parent:\n{parent_context}"})
                messages.append({"role": "user", "content": task.task_description})

                spec = AgentRunSpec(
                    messages=messages,
                    tools=self._tools,
                    provider=self._provider,
                    max_iterations=self._max_iterations,
                    system=self._system_prompt or None,
                )

                task.result = await self._runner.run(spec)
                task.status = "completed"
                task.completed_at = datetime.now()

            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.completed_at = datetime.now()
                logger.error(f"Subagent {task.id} failed: {e}")
            finally:
                task.event.set()

    def get_task(self, task_id: str) -> SubagentTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[SubagentTask]:
        return list(self._tasks.values())

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == "running")

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == "completed")
