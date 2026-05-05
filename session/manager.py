from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .session import Session


class SessionManager:
    """Session manager with JSONL persistence and crash recovery."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._sessions: dict[str, Session] = {}
        self._storage_dir: Path | None = Path(storage_dir) if storage_dir else None
        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create(self, key: str) -> Session:
        """Get an existing session (from memory or disk) or create a new one."""
        if key in self._sessions:
            return self._sessions[key]
        loaded = self._load_from_disk(key)
        if loaded:
            self._sessions[key] = loaded
            return loaded
        session = Session(key=key)
        self._sessions[key] = session
        return session

    def save(self, session: Session) -> None:
        """Save session to memory and append to JSONL file."""
        self._sessions[session.key] = session
        self._append_to_jsonl(session)

    def get(self, key: str) -> Session | None:
        """Get session by key, or None if not found."""
        if key in self._sessions:
            return self._sessions[key]
        loaded = self._load_from_disk(key)
        if loaded:
            self._sessions[key] = loaded
        return loaded

    def list_sessions(self) -> list[str]:
        """List all session keys (in-memory + on disk)."""
        keys = set(self._sessions.keys())
        if self._storage_dir:
            for f in self._storage_dir.glob("*.jsonl"):
                keys.add(f.stem)
        return list(keys)

    def recover(self, key: str) -> Session | None:
        """
        Load session and check for crash recovery state.
        Returns session with recovery info in metadata, or None.
        """
        session = self.get(key)
        if session and session.has_pending_user_turn():
            return session
        return session

    # --- JSONL persistence ---

    def _jsonl_path(self, key: str) -> Path | None:
        if self._storage_dir:
            safe_key = key.replace(":", "_").replace("/", "_").replace("\\", "_")
            return self._storage_dir / f"{safe_key}.jsonl"
        return None

    def _append_to_jsonl(self, session: Session) -> None:
        """Append current session state as a single JSONL line."""
        path = self._jsonl_path(session.key)
        if path is None:
            return
        entry = {
            "type": "snapshot",
            "timestamp": datetime.now().isoformat(),
            **session.to_dict(),
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _load_from_disk(self, key: str) -> Session | None:
        """Replay JSONL file to reconstruct session."""
        path = self._jsonl_path(key)
        if path is None or not path.exists():
            return None

        session = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("type") == "snapshot":
                    session = Session.from_dict(entry)
        return session
