"""
Per-user workspace isolation.

Directory layout:
    workspace/
    ├── _default/              ← templates (copied on first access)
    │   ├── IDENTITY.md
    │   ├── SOUL.md
    │   └── skills/
    └── users/
        ├── user_alice/        ← Alice's isolated workspace
        │   ├── IDENTITY.md
        │   ├── SOUL.md
        │   ├── MEMORY.md
        │   ├── history.jsonl
        │   ├── skills/
        │   └── projects/
        └── user_bob/
            └── ...
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path


class UserWorkspace:
    """
    Manages per-user workspace directories.
    Thread-safe: each user's initialization is locked independently.
    """

    def __init__(self, base_workspace: str) -> None:
        self._base = Path(base_workspace).resolve()
        self._default_dir = self._base / "_default"
        self._users_dir = self._base / "users"
        self._users_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        # Current user context (set per-message)
        self._current_user: str | None = None

    @property
    def base_workspace(self) -> Path:
        return self._base

    def set_current_user(self, user_id: str) -> None:
        """Set the current user context (call before processing a message)."""
        self._current_user = self._sanitize(user_id)

    def get_current_user(self) -> str | None:
        return self._current_user

    def resolve(self, user_id: str | None = None) -> Path:
        """Get the workspace directory for a user. Initializes from _default if needed."""
        uid = self._sanitize(user_id or self._current_user or "default")
        user_dir = self._users_dir / uid

        # Fast path: already initialized
        if user_dir.exists():
            return user_dir

        # Slow path: initialize with lock
        lock = self._get_lock(uid)
        with lock:
            # Double-check after acquiring lock
            if user_dir.exists():
                return user_dir
            self._init_user_dir(uid, user_dir)
            return user_dir

    def _init_user_dir(self, uid: str, user_dir: Path) -> None:
        """Initialize a user directory from _default template."""
        user_dir.mkdir(parents=True, exist_ok=True)

        if self._default_dir.exists():
            # Copy template files
            for item in self._default_dir.iterdir():
                dest = user_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    if not dest.exists():
                        shutil.copy2(item, dest)
        else:
            # No template — create minimal defaults
            self._create_minimal_defaults(user_dir)

        # Ensure MEMORY.md exists (not in template — user-specific)
        memory_file = user_dir / "MEMORY.md"
        if not memory_file.exists():
            memory_file.write_text("", encoding="utf-8")

        # Ensure projects dir exists
        projects_dir = user_dir / "projects"
        projects_dir.mkdir(exist_ok=True)

    def _create_minimal_defaults(self, user_dir: Path) -> None:
        """Create minimal default files when no template exists."""
        identity = user_dir / "IDENTITY.md"
        if not identity.exists():
            identity.write_text(
                "You are Dragon Agent, a helpful AI assistant.\n"
                "Be concise and helpful.\n",
                encoding="utf-8",
            )

        soul = user_dir / "SOUL.md"
        if not soul.exists():
            soul.write_text(
                "Be direct and efficient. Prefer showing over telling.\n"
                "When you don't know something, say so rather than guessing.\n",
                encoding="utf-8",
            )

        skills_dir = user_dir / "skills"
        skills_dir.mkdir(exist_ok=True)

    def _get_lock(self, uid: str) -> threading.Lock:
        """Get or create a per-user lock."""
        with self._global_lock:
            if uid not in self._locks:
                self._locks[uid] = threading.Lock()
            return self._locks[uid]

    @staticmethod
    def _sanitize(user_id: str) -> str:
        """Sanitize user_id for use as directory name."""
        # Replace characters that are unsafe for directory names
        safe = user_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        safe = safe.replace(" ", "_").replace(".", "_")
        # Collapse multiple underscores
        while "__" in safe:
            safe = safe.replace("__", "_")
        return safe.strip("_") or "default"
