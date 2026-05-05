from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .workspace import UserWorkspace


class MemoryStore:
    """
    File-based memory: MEMORY.md as index + history.jsonl for archived memories.
    Supports per-user workspace isolation via UserWorkspace.
    """

    def __init__(self, workspace: str | UserWorkspace = ".") -> None:
        if isinstance(workspace, UserWorkspace):
            self._user_workspace = workspace
            self._static_workspace = None
        else:
            self._user_workspace = None
            self._static_workspace = Path(workspace)

    def _resolve_workspace(self) -> Path:
        """Resolve workspace path for the current user."""
        if self._user_workspace:
            return self._user_workspace.resolve()
        return self._static_workspace

    def _memory_file(self) -> Path:
        return self._resolve_workspace() / "MEMORY.md"

    def _history_file(self) -> Path:
        return self._resolve_workspace() / "history.jsonl"

    def load(self) -> str:
        """Load MEMORY.md content for injection into prompt."""
        p = self._memory_file()
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
        return ""

    def save_entry(self, name: str, content: str, entry_type: str = "note") -> None:
        """Append a memory entry to MEMORY.md and archive to history.jsonl."""
        timestamp = datetime.now().isoformat()

        # Append to MEMORY.md
        entry_line = f"- **{name}** ({entry_type}, {timestamp}): {content}\n"
        with open(self._memory_file(), "a", encoding="utf-8") as f:
            f.write(entry_line)

        # Archive to history.jsonl
        record = {
            "type": entry_type,
            "name": name,
            "content": content,
            "timestamp": timestamp,
        }
        with open(self._history_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def list_entries(self) -> list[dict]:
        """List all entries from history.jsonl."""
        p = self._history_file()
        if not p.exists():
            return []
        entries = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def clear(self) -> None:
        """Clear all memory."""
        mf = self._memory_file()
        hf = self._history_file()
        if mf.exists():
            mf.write_text("")
        if hf.exists():
            hf.write_text("")
