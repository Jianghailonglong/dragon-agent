from __future__ import annotations

from typing import Any

from tools.base import BaseTool
from orchestration.subagent import SubagentManager


class SubagentStatusTool(BaseTool):
    """Check the status of a spawned subagent task."""

    def __init__(self, manager: SubagentManager) -> None:
        self._manager = manager

    @property
    def name(self) -> str:
        return "subagent_status"

    @property
    def description(self) -> str:
        return "Check the status and result of a spawned subagent task."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task_id returned by subagent_spawn.",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        task_id = kwargs["task_id"]
        task = self._manager.get_task(task_id)

        if task is None:
            return f"Unknown task: {task_id}"

        if task.status == "pending":
            return f"Task {task_id} is pending."
        if task.status == "running":
            return f"Task {task_id} is running."
        if task.status == "failed":
            return f"Task {task_id} failed: {task.error}"
        if task.status == "completed" and task.result:
            return task.result.content or "(subagent completed with no output)"

        return f"Task {task_id} status: {task.status}"
