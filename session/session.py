from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Session:
    """A conversation session with JSONL persistence and crash recovery."""
    key: str
    messages: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str | list) -> None:
        """Add a message to the session."""
        msg = {"role": role, "content": content}
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def add_tool_result(self, tool_use_id: str, result: str) -> None:
        """Add a tool result message."""
        self.messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": result}],
        })
        self.updated_at = datetime.now()

    def get_messages(self) -> list[dict]:
        """Return a copy of messages."""
        return list(self.messages)

    # --- Checkpoint helpers ---

    def mark_pending_user_turn(self) -> None:
        """Mark that a user turn is in progress (for crash recovery)."""
        self.metadata["pending_user_turn"] = True

    def clear_pending_user_turn(self) -> None:
        self.metadata.pop("pending_user_turn", None)

    def has_pending_user_turn(self) -> bool:
        return self.metadata.get("pending_user_turn", False)

    def set_runtime_checkpoint(self, checkpoint: dict) -> None:
        """Save a runtime checkpoint (e.g. last completed tool index)."""
        self.metadata["runtime_checkpoint"] = checkpoint

    def get_runtime_checkpoint(self) -> dict | None:
        return self.metadata.get("runtime_checkpoint")

    def clear_runtime_checkpoint(self) -> None:
        self.metadata.pop("runtime_checkpoint", None)

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "messages": self.messages,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Session:
        return cls(
            key=data["key"],
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )
