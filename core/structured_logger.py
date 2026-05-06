from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from typing import Any

# Context variables for structured log enrichment
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_session_key: ContextVar[str] = ContextVar("session_key", default="")


class StructuredLogger:
    """
    Structured JSON logger for agent lifecycle events.
    Wraps standard logging with consistent context fields.
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def set_context(self, request_id: str = "", session_key: str = "") -> None:
        """Set context for subsequent log entries."""
        if request_id:
            _request_id.set(request_id)
        if session_key:
            _session_key.set(session_key)

    def _log(self, level: int, event: str, **fields: Any) -> None:
        if not self._logger.isEnabledFor(level):
            return

        record = {
            "event": event,
            "request_id": _request_id.get(),
            "session_key": _session_key.get(),
            **fields,
        }
        # Remove empty fields
        record = {k: v for k, v in record.items() if v}

        self._logger.log(level, json.dumps(record, ensure_ascii=False, default=str))

    def llm_call_start(self, model: str, message_count: int) -> None:
        self._log(logging.INFO, "llm_call_start", model=model, message_count=message_count)

    def llm_call_end(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        stop_reason: str,
    ) -> None:
        self._log(
            logging.INFO, "llm_call_end",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=round(duration_ms, 1),
            stop_reason=stop_reason,
        )

    def llm_call_error(self, model: str, error: str, duration_ms: float) -> None:
        self._log(
            logging.WARNING, "llm_call_error",
            model=model, error=error, duration_ms=round(duration_ms, 1)
        )

    def tool_execute(self, tool_name: str, duration_ms: float, success: bool, error: str = "") -> None:
        fields: dict[str, Any] = {
            "tool_name": tool_name,
            "duration_ms": round(duration_ms, 1),
            "success": success,
        }
        if error:
            fields["error"] = error
        self._log(logging.INFO, "tool_execute", **fields)

    def checkpoint(self, tool_index: int, tool_name: str) -> None:
        self._log(logging.INFO, "checkpoint", tool_index=tool_index, tool_name=tool_name)

    def retry(self, attempt: int, max_retries: int, error: str) -> None:
        self._log(
            logging.WARNING, "retry",
            attempt=attempt, max_retries=max_retries, error=error
        )

    def error(self, error_type: str, error_message: str, iteration: int = 0, **extra: Any) -> None:
        self._log(
            logging.ERROR, "agent_error",
            error_type=error_type,
            error_message=error_message,
            iteration=iteration,
            **extra,
        )


def timer() -> float:
    """Return a monotonic timestamp for duration measurement."""
    return time.monotonic()


def elapsed_ms(start: float) -> float:
    """Calculate elapsed milliseconds since start."""
    return (time.monotonic() - start) * 1000
