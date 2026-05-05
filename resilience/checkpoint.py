from __future__ import annotations

from session.session import Session
from session.manager import SessionManager


class CheckpointManager:
    """
    Manages crash recovery checkpoints in session metadata.
    - Marks pending user turns before processing
    - Saves runtime checkpoints after each tool execution
    - Recovers interrupted sessions on restart
    """

    def __init__(self, session_manager: SessionManager) -> None:
        self._sessions = session_manager

    def begin_user_turn(self, session: Session) -> None:
        """Mark that a user turn is about to be processed."""
        session.mark_pending_user_turn()
        self._sessions.save(session)

    def commit_user_turn(self, session: Session) -> None:
        """User turn fully processed, clear pending marker."""
        session.clear_pending_user_turn()
        session.clear_runtime_checkpoint()
        self._sessions.save(session)

    def save_tool_checkpoint(self, session: Session, tool_index: int, tool_name: str) -> None:
        """Save checkpoint after a tool finishes execution."""
        session.set_runtime_checkpoint({
            "last_completed_tool_index": tool_index,
            "last_completed_tool_name": tool_name,
        })
        self._sessions.save(session)

    def recover(self, session_key: str) -> tuple[Session | None, str]:
        """
        Attempt to recover a session after a crash.
        Returns (session, status) where status is:
        - "clean": no pending work
        - "recovered": had pending turn, marked as interrupted
        """
        session = self._sessions.recover(session_key)
        if session is None:
            return None, "not_found"

        if session.has_pending_user_turn():
            # Crash happened mid-processing
            checkpoint = session.get_runtime_checkpoint()
            if checkpoint:
                # Append a marker about the interruption
                session.add_message("assistant", (
                    f"[System: Previous turn was interrupted after tool "
                    f"'{checkpoint.get('last_completed_tool_name', 'unknown')}' "
                    f"(index {checkpoint.get('last_completed_tool_index', '?')}). "
                    f"Please acknowledge and continue.]"
                ))
            else:
                session.add_message("assistant", (
                    "[System: Previous turn was interrupted before any tools executed. "
                    "Please re-process the last user message.]"
                ))

            session.clear_pending_user_turn()
            session.clear_runtime_checkpoint()
            self._sessions.save(session)
            return session, "recovered"

        return session, "clean"

    def scan_for_interrupted(self) -> list[str]:
        """Scan all sessions for interrupted turns."""
        interrupted = []
        for key in self._sessions.list_sessions():
            session = self._sessions.get(key)
            if session and session.has_pending_user_turn():
                interrupted.append(key)
        return interrupted

    def recover_all(self) -> dict[str, str]:
        """Recover all interrupted sessions. Returns {key: status}."""
        results = {}
        for key in self.scan_for_interrupted():
            _, status = self.recover(key)
            results[key] = status
        return results
