from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name used by LLM."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the LLM."""

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema for the tool parameters."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return the result as a string."""

    def to_schema(self) -> dict:
        """Return the tool schema in the format expected by LLM APIs."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
