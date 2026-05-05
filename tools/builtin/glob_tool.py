from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base import BaseTool
from intelligence.workspace import UserWorkspace


class GlobTool(BaseTool):
    """Find files matching a glob pattern."""

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
        return "glob"

    @property
    def description(self) -> str:
        return "Find files matching a glob pattern. Returns sorted file paths."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')."},
                "path": {"type": "string", "description": "Directory to search in.", "default": "."},
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workspace = self._resolve_workspace()
        pattern = kwargs["pattern"]
        search_dir = kwargs.get("path", ".")

        search_path = Path(search_dir)
        if not search_path.is_absolute():
            search_path = workspace / search_path
        search_path = search_path.resolve()

        if not str(search_path).startswith(str(workspace)):
            return "Error: path is outside workspace boundary."

        try:
            files = sorted(search_path.rglob(pattern))
            rel_files = []
            for f in files:
                if f.is_file():
                    try:
                        rel_files.append(str(f.relative_to(workspace)))
                    except ValueError:
                        rel_files.append(str(f))
                    if len(rel_files) >= 200:
                        break
            return "\n".join(rel_files) if rel_files else "(no files found)"
        except Exception as e:
            return f"Error: {e}"
