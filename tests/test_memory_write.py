"""Tests for memory_write tool and Phase 1 intelligence wiring."""
import pytest
import pytest_asyncio

from intelligence.memory import MemoryStore
from intelligence.context import ContextBuilder
from intelligence.skills import SkillsLoader, Skill
from tools.builtin.memory_write import MemoryWriteTool


@pytest.mark.asyncio
async def test_memory_write_saves(tmp_path):
    memory = MemoryStore(workspace=str(tmp_path))
    tool = MemoryWriteTool(memory=memory)

    assert tool.name == "memory_write"

    result = await tool.execute(name="user_lang", content="Python", entry_type="user")
    assert "saved" in result.lower()

    # Verify MEMORY.md was written
    mem_file = tmp_path / "MEMORY.md"
    assert mem_file.exists()
    text = mem_file.read_text()
    assert "user_lang" in text
    assert "Python" in text

    # Verify history.jsonl was written
    entries = memory.list_entries()
    assert len(entries) == 1
    assert entries[0]["name"] == "user_lang"
    assert entries[0]["type"] == "user"


def test_context_builder_with_memory(tmp_path):
    # Write MEMORY.md
    mem = tmp_path / "MEMORY.md"
    mem.write_text("- **user_name**: Alice\n- **project_lang**: Python\n", encoding="utf-8")

    ctx = ContextBuilder(workspace=str(tmp_path))
    prompt = ctx.build_system_prompt(channel="cli")
    assert "Alice" in prompt
    assert "Python" in prompt


def test_context_builder_default_identity(tmp_path):
    """Default identity includes tool usage guidance."""
    ctx = ContextBuilder(workspace=str(tmp_path))
    prompt = ctx.build_system_prompt(channel="cli")
    assert "Dragon Agent" in prompt
    assert "Only use tools" in prompt


def test_context_builder_custom_identity(tmp_path):
    """IDENTITY.md overrides default."""
    ident = tmp_path / "IDENTITY.md"
    ident.write_text("You are Jarvis.", encoding="utf-8")

    ctx = ContextBuilder(workspace=str(tmp_path))
    prompt = ctx.build_system_prompt(channel="cli")
    assert "Jarvis" in prompt
    assert "Dragon Agent" not in prompt


def test_skills_loader_in_context(tmp_path):
    """Skills are injected into system prompt."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        '---\nname: test-skill\ndescription: A test\nalways_on: true\n---\nDo something.',
        encoding="utf-8",
    )

    loader = SkillsLoader(workspace=str(tmp_path))
    always_on = loader.load_always_on()
    assert "test-skill" in always_on

    ctx = ContextBuilder(workspace=str(tmp_path))
    prompt = ctx.build_system_prompt(channel="cli", skills=always_on)
    assert "test-skill" in prompt
