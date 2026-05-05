import pytest
from pathlib import Path

from intelligence.context import ContextBuilder


def test_context_builder_with_workspace(tmp_path):
    (tmp_path / "IDENTITY.md").write_text("I am Test Agent.")
    (tmp_path / "SOUL.md").write_text("Be helpful.")

    cb = ContextBuilder(workspace=str(tmp_path))
    prompt = cb.build_system_prompt(channel="cli")

    assert "I am Test Agent." in prompt
    assert "Be helpful." in prompt
    assert "CLI" in prompt.lower() or "cli" in prompt


def test_context_builder_no_files(tmp_path):
    cb = ContextBuilder(workspace=str(tmp_path))
    prompt = cb.build_system_prompt(channel="telegram")
    assert "Telegram" in prompt or "telegram" in prompt


def test_context_builder_with_skills(tmp_path):
    cb = ContextBuilder(workspace=str(tmp_path))
    prompt = cb.build_system_prompt(skills=["code-review", "testing"])
    assert "code-review" in prompt
    assert "testing" in prompt


def test_context_builder_with_memory(tmp_path):
    (tmp_path / "MEMORY.md").write_text("- User prefers Python")
    cb = ContextBuilder(workspace=str(tmp_path))
    prompt = cb.build_system_prompt()
    assert "User prefers Python" in prompt
