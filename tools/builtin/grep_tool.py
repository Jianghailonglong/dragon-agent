from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.base import BaseTool
from intelligence.workspace import UserWorkspace


class GrepTool(BaseTool):
    """Search for a pattern in files."""

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
        return "grep"

    @property
    def description(self) -> str:
        return "Search for a regex pattern in files. Returns matching lines with file paths and line numbers."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for."},
                "glob": {"type": "string", "description": "Glob pattern to filter files (e.g. '*.py').", "default": "*"},
                "path": {"type": "string", "description": "Directory to search in.", "default": "."},
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workspace = self._resolve_workspace()
        pattern = kwargs["pattern"]
        glob_pattern = kwargs.get("glob", "*")
        search_dir = kwargs.get("path", ".")

        search_path = Path(search_dir)
        if not search_path.is_absolute():
            search_path = workspace / search_path
        search_path = search_path.resolve()

        if not str(search_path).startswith(str(workspace)):
            return "Error: path is outside workspace boundary."

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Error: invalid regex: {e}"

        matches = []
        try:
            for file_path in search_path.rglob(glob_pattern):
                if not file_path.is_file():
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(text.splitlines(), 1):
                        if regex.search(line):
                            rel = file_path.relative_to(workspace)
                            matches.append(f"{rel}:{i}: {line}")
                            if len(matches) >= 100:
                                break
                except Exception:
                    continue
                if len(matches) >= 100:
                    break
        except Exception as e:
            return f"Error searching: {e}"

        return "\n".join(matches) if matches else "(no matches)"
