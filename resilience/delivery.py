from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable

from core.types import OutboundMessage

logger = logging.getLogger(__name__)


@dataclass
class DeliveryEntry:
    """A pending delivery in the queue."""
    id: str
    message: OutboundMessage
    attempts: int = 0
    max_attempts: int = 5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_error: str = ""


class DeliveryQueue:
    """
    Write-Ahead Delivery Queue:
    1. Persist entry to disk before attempting delivery
    2. Attempt to send via channel
    3. On success, mark as delivered
    4. On failure, keep in queue for retry with exponential backoff
    """

    def __init__(
        self,
        storage_dir: str | Path,
        send_fn: Callable[[OutboundMessage], Awaitable[None]],
    ) -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._send_fn = send_fn
        self._queue: dict[str, DeliveryEntry] = {}
        self._counter = 0

        # Load pending entries from disk
        self._load_pending()

    async def enqueue(self, msg: OutboundMessage) -> str:
        """
        Add message to delivery queue.
        Returns entry ID.
        """
        self._counter += 1
        entry_id = f"del_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._counter}"
        entry = DeliveryEntry(id=entry_id, message=msg)

        # Write-ahead: persist before sending
        self._persist_entry(entry)
        self._queue[entry_id] = entry

        # Attempt immediate delivery
        await self._try_deliver(entry_id)
        return entry_id

    async def retry_pending(self) -> int:
        """Retry all pending deliveries. Returns number of successful sends."""
        success = 0
        for entry_id in list(self._queue.keys()):
            entry = self._queue[entry_id]
            if entry.attempts >= entry.max_attempts:
                logger.error(f"Delivery {entry_id} exceeded max attempts, dropping")
                self._remove_entry(entry_id)
                continue

            ok = await self._try_deliver(entry_id)
            if ok:
                success += 1
        return success

    def pending_count(self) -> int:
        return len(self._queue)

    def get_entry(self, entry_id: str) -> DeliveryEntry | None:
        return self._queue.get(entry_id)

    async def _try_deliver(self, entry_id: str) -> bool:
        """Attempt to deliver a single entry."""
        entry = self._queue.get(entry_id)
        if entry is None:
            return False

        entry.attempts += 1
        try:
            await self._send_fn(entry.message)
            self._remove_entry(entry_id)
            return True
        except Exception as e:
            entry.last_error = str(e)
            self._persist_entry(entry)
            logger.warning(f"Delivery {entry_id} failed (attempt {entry.attempts}): {e}")
            return False

    def _persist_entry(self, entry: DeliveryEntry) -> None:
        """Write entry to disk."""
        path = self._storage_dir / f"{entry.id}.json"
        data = {
            "id": entry.id,
            "channel": entry.message.channel,
            "chat_id": entry.message.chat_id,
            "content": entry.message.content,
            "attempts": entry.attempts,
            "max_attempts": entry.max_attempts,
            "created_at": entry.created_at,
            "last_error": entry.last_error,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _remove_entry(self, entry_id: str) -> None:
        """Remove entry from queue and disk."""
        self._queue.pop(entry_id, None)
        path = self._storage_dir / f"{entry_id}.json"
        if path.exists():
            path.unlink()

    def _load_pending(self) -> None:
        """Load pending entries from disk on startup."""
        for path in self._storage_dir.glob("del_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                msg = OutboundMessage(
                    channel=data["channel"],
                    chat_id=data["chat_id"],
                    content=data["content"],
                )
                entry = DeliveryEntry(
                    id=data["id"],
                    message=msg,
                    attempts=data.get("attempts", 0),
                    max_attempts=data.get("max_attempts", 5),
                    created_at=data.get("created_at", ""),
                    last_error=data.get("last_error", ""),
                )
                self._queue[entry.id] = entry
            except Exception as e:
                logger.error(f"Failed to load delivery entry {path}: {e}")
