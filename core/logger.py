from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class ConversationLogger:
    """Logs conversation messages to local files."""

    def __init__(self, log_dir: str | Path = "logs") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def log_user_message(self, session_key: str, content: str) -> None:
        """Log a user message."""
        self._append(session_key, {
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def log_assistant_message(self, session_key: str, content: str, iterations: int = 0, usage: dict | None = None) -> None:
        """Log an assistant response."""
        entry = {
            "role": "assistant",
            "content": content,
            "iterations": iterations,
            "timestamp": datetime.now().isoformat(),
        }
        if usage:
            entry["usage"] = usage
        self._append(session_key, entry)

    def log_tool_call(self, session_key: str, tool_name: str, args: dict, result: str) -> None:
        """Log a tool call and its result."""
        self._append(session_key, {
            "role": "tool",
            "tool_name": tool_name,
            "args": args,
            "result": result[:2000],  # truncate long results in log
            "timestamp": datetime.now().isoformat(),
        })

    def log_error(self, session_key: str, error: str) -> None:
        """Log an error."""
        self._append(session_key, {
            "role": "error",
            "content": error,
            "timestamp": datetime.now().isoformat(),
        })

    def _append(self, session_key: str, entry: dict) -> None:
        """Append an entry to the session's log file."""
        safe_key = session_key.replace(":", "_").replace("/", "_")
        log_file = self._log_dir / f"{safe_key}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_log_path(self, session_key: str) -> Path:
        safe_key = session_key.replace(":", "_").replace("/", "_")
        return self._log_dir / f"{safe_key}.jsonl"
