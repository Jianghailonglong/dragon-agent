from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base import BaseTool
from intelligence.workspace import UserWorkspace


class WriteFileTool(BaseTool):
    """Write content to a file."""

    def __init__(self, workspace: str | UserWorkspace = ".") -> None:
        if isinstance(workspace, UserWorkspace):
            self._user_workspace = workspace
            self._static_workspace = None
        else:
            self._user_workspace = None
            self._static_workspace = Path(workspace).resolve()

    def _resolve_workspace(self) -> Path:
        if self._user_workspace:
            return self._user_workspace.resolve()
        return self._static_workspace

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write to."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workspace = self._resolve_workspace()
        path = Path(kwargs["path"])
        if not path.is_absolute():
            path = workspace / path
        path = path.resolve()

        if not str(path).startswith(str(workspace)):
            return "Error: path is outside workspace boundary."

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(kwargs["content"], encoding="utf-8")
            return f"Wrote {len(kwargs['content'])} chars to {path}"
        except Exception as e:
            return f"Error writing file: {e}"
