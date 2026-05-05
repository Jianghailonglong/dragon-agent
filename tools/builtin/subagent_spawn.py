from __future__ import annotations

from typing import Any

from tools.base import BaseTool
from orchestration.subagent import SubagentManager


class SubagentSpawnTool(BaseTool):
    """Spawn a subagent to handle a task in parallel."""

    def __init__(self, manager: SubagentManager) -> None:
        self._manager = manager

    @property
    def name(self) -> str:
        return "subagent_spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task independently and in parallel. "
            "The subagent has access to the same tools. Use this for tasks that "
            "can be done independently, like researching a topic while you continue "
            "another task. Returns a task_id you can use to check status."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of what the subagent should do.",
                },
                "context": {
                    "type": "string",
                    "description": "Optional context from the current conversation to pass to the subagent.",
                    "default": "",
                },
                "wait": {
                    "type": "boolean",
                    "description": "If true, wait for the result before returning. If false, return task_id immediately.",
                    "default": False,
                },
            },
            "required": ["task"],
        }

    async def execute(self, **kwargs: Any) -> str:
        task = kwargs["task"]
        context = kwargs.get("context", "")
        wait = kwargs.get("wait", False)

        if wait:
            result = await self._manager.spawn_and_wait(task, parent_context=context)
            return result.content or "(subagent produced no output)"

        task_id = await self._manager.spawn(task, parent_context=context)
        return f"Subagent spawned with task_id: {task_id}. Use subagent_status(task_id='{task_id}') to check progress."
