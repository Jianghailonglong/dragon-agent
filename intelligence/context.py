from __future__ import annotations

from pathlib import Path

from .workspace import UserWorkspace


class ContextBuilder:
    """8-layer system prompt assembly. Supports per-user workspace isolation."""

    def __init__(self, workspace: str | UserWorkspace = ".") -> None:
        if isinstance(workspace, UserWorkspace):
            self._user_workspace = workspace
            self._static_workspace = None
        else:
            self._user_workspace = None
            self._static_workspace = Path(workspace)

    def _resolve_workspace(self) -> Path:
        if self._user_workspace:
            return self._user_workspace.resolve()
        return self._static_workspace

    def build_system_prompt(
        self,
        channel: str = "cli",
        skills: list[str] | None = None,
        extra: str = "",
    ) -> str:
        parts = [
            self._layer_identity(),
            self._layer_soul(),
            self._layer_tools_guidance(),
            self._layer_skills(skills or []),
            self._layer_memory(),
            self._layer_bootstrap(),
            self._layer_runtime_context(channel),
            self._layer_channel_hints(channel),
        ]
        if extra:
            parts.append(extra)

        return "\n\n---\n\n".join(p for p in parts if p)

    def _layer_identity(self) -> str:
        path = self._resolve_workspace() / "IDENTITY.md"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        return (
            "You are Dragon Agent, a helpful AI assistant.\n"
            "Answer questions directly and concisely. "
            "Only use tools when the user explicitly asks you to perform an action "
            "(read a file, run a command, search code, etc.) or when you genuinely need "
            "external information that you don't know. "
            "Do NOT use tools for simple questions you can answer from your own knowledge."
        )

    def _layer_soul(self) -> str:
        path = self._resolve_workspace() / "SOUL.md"
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def _layer_tools_guidance(self) -> str:
        path = self._resolve_workspace() / "TOOLS.md"
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def _layer_skills(self, skill_names: list[str]) -> str:
        if not skill_names:
            return ""
        return "Active skills:\n" + "\n".join(f"- {s}" for s in skill_names)

    def _layer_memory(self) -> str:
        path = self._resolve_workspace() / "MEMORY.md"
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def _layer_bootstrap(self) -> str:
        path = self._resolve_workspace() / "BOOTSTRAP.md"
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def _layer_runtime_context(self, channel: str) -> str:
        return f"Current channel: {channel}"

    def _layer_channel_hints(self, channel: str) -> str:
        hints = {
            "cli": "You are running in a CLI. Be concise. Use plain text.",
            "telegram": "You are chatting via Telegram. Keep messages short. Markdown is supported.",
            "feishu": "You are chatting via Feishu (Lark). Use clear formatting.",
            "wechat": "You are chatting via WeChat. Keep responses brief.",
        }
        return hints.get(channel, "")
