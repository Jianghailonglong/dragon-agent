from __future__ import annotations

from typing import Any

from tools.base import BaseTool


class AskUserTool(BaseTool):
    """Ask the user a question and wait for input."""

    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return "Ask the user a question and wait for their response."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user.",
                },
            },
            "required": ["question"],
        }

    async def execute(self, **kwargs: Any) -> str:
        question = kwargs["question"]
        # In CLI mode, this will be overridden by the channel
        # For now, use basic input
        print(f"\n🤖 Agent asks: {question}")
        try:
            response = input("Your answer: ")
            return response
        except (EOFError, KeyboardInterrupt):
            return "(user cancelled)"
