from __future__ import annotations

import asyncio
import sys
import threading
from typing import Callable

from .base import BaseChannel
from core.types import InboundMessage, OutboundMessage


class Spinner:
    """Terminal spinner animation for loading states."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Thinking") -> None:
        self._message = message
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        # Clear the spinner line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def _animate(self) -> None:
        i = 0
        while self._running:
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r  {frame} {self._message}...")
            sys.stdout.flush()
            i += 1
            # Check every 80ms
            import time
            time.sleep(0.08)


class CLIChannel(BaseChannel):
    """CLI channel that reads from stdin and writes to stdout."""

    def __init__(self, show_spinner: bool = True) -> None:
        self._chat_id = "cli:local"
        self._sender_id = "user"
        self._show_spinner = show_spinner
        self._spinner: Spinner | None = None

    @property
    def name(self) -> str:
        return "cli"

    async def connect(self) -> None:
        print("\n  Dragon Agent is ready!")
        print("  Type your message below. Ctrl+C to exit.\n")

    async def receive(self) -> InboundMessage:
        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(None, self._read_input)
            return InboundMessage(
                channel="cli",
                sender_id=self._sender_id,
                chat_id=self._chat_id,
                content=content,
            )
        except asyncio.CancelledError:
            # Graceful shutdown on Ctrl+C
            raise SystemExit(0)

    async def send(self, msg: OutboundMessage) -> None:
        self.stop_spinner()
        print(f"\n  🌟 {msg.content}\n")

    def start_spinner(self, message: str = "Thinking") -> None:
        if self._show_spinner:
            self.stop_spinner()
            self._spinner = Spinner(message)
            self._spinner.start()

    def stop_spinner(self) -> None:
        if self._spinner:
            self._spinner.stop()
            self._spinner = None

    def _read_input(self) -> str:
        try:
            return input("  🐉 > ")
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0)
