from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from intelligence.workspace import UserWorkspace


class ExecTool(BaseTool):
    """Execute a shell command."""

    def __init__(self, workspace: str | UserWorkspace = ".", timeout: int = 30) -> None:
        if isinstance(workspace, UserWorkspace):
            self._user_workspace = workspace
            self._static_workspace = None
        else:
            self._user_workspace = None
            self._static_workspace = Path(workspace).resolve()
        self._timeout = timeout

    def _resolve_workspace(self) -> Path:
        if self._user_workspace:
            return self._user_workspace.resolve()
        return self._static_workspace

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return stdout/stderr."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: Any) -> str:
        command = kwargs["command"]
        workspace = self._resolve_workspace()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(workspace),
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            output = stdout.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                return f"[exit code {proc.returncode}]\n{output}"
            return output or "(no output)"
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: command timed out after {self._timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
