from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base import BaseTool
from intelligence.workspace import UserWorkspace


class EditFileTool(BaseTool):
    """Edit a file by replacing a string."""

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
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old_string with new_string."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit."},
                "old_string": {"type": "string", "description": "String to find and replace."},
                "new_string": {"type": "string", "description": "Replacement string."},
            },
            "required": ["path", "old_string", "new_string"],
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

        try:
            text = path.read_text(encoding="utf-8")
            old = kwargs["old_string"]
            new = kwargs["new_string"]
            if old not in text:
                return f"Error: old_string not found in {path}"
            count = text.count(old)
            new_text = text.replace(old, new)
            path.write_text(new_text, encoding="utf-8")
            return f"Replaced {count} occurrence(s) in {path}"
        except Exception as e:
            return f"Error editing file: {e}"
