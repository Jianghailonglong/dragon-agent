import pytest
from pathlib import Path

from intelligence.skills import SkillsLoader


def _create_skill(skills_dir: Path, name: str, body: str, always_on: bool = False):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = f"---\nname: {name}\ndescription: Test skill\nalways_on: {'true' if always_on else 'false'}\n---"
    (skill_dir / "SKILL.md").write_text(f"{frontmatter}\n{body}")


def test_discover_skills(tmp_path):
    skills_dir = tmp_path / "skills"
    _create_skill(skills_dir, "skill-a", "Do thing A")
    _create_skill(skills_dir, "skill-b", "Do thing B")

    loader = SkillsLoader(workspace=str(tmp_path))
    skills = loader.discover()
    assert len(skills) == 2
    names = [s.name for s in skills]
    assert "skill-a" in names
    assert "skill-b" in names


def test_always_on_filter(tmp_path):
    skills_dir = tmp_path / "skills"
    _create_skill(skills_dir, "always", "Always active", always_on=True)
    _create_skill(skills_dir, "optional", "Optional", always_on=False)

    loader = SkillsLoader(workspace=str(tmp_path))
    names = loader.load_always_on()
    assert names == ["always"]


def test_load_skill_body(tmp_path):
    skills_dir = tmp_path / "skills"
    _create_skill(skills_dir, "my-skill", "When invoked, do something important.")

    loader = SkillsLoader(workspace=str(tmp_path))
    body = loader.load_skill_body("my-skill")
    assert "do something important" in body


def test_no_skills_dir(tmp_path):
    loader = SkillsLoader(workspace=str(tmp_path))
    assert loader.discover() == []
    assert loader.load_always_on() == []
