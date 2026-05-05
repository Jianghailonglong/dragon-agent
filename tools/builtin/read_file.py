from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base import BaseTool
from intelligence.workspace import UserWorkspace


class ReadFileTool(BaseTool):
    """Read file contents from the workspace."""

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
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative or absolute file path to read.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-based).",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of lines to read.",
                    "default": 2000,
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workspace = self._resolve_workspace()
        path = Path(kwargs["path"])
        if not path.is_absolute():
            path = workspace / path

        path = path.resolve()
        if not str(path).startswith(str(workspace)):
            return "Error: path is outside workspace boundary."

        if not path.exists():
            return f"Error: file not found: {path}"

        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 2000)

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = lines[offset:offset + limit]
            return "\n".join(selected)
        except Exception as e:
            return f"Error reading file: {e}"
