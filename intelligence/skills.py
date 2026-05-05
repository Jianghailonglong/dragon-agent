from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .workspace import UserWorkspace


@dataclass
class Skill:
    """A loaded skill from a SKILL.md file."""
    name: str
    description: str
    always_on: bool
    body: str


class SkillsLoader:
    """
    Discover and load skills from workspace/skills/ directory.
    Each skill is a SKILL.md file with YAML frontmatter + Markdown body.
    Supports per-user workspace isolation.
    """

    def __init__(self, workspace: str | UserWorkspace = ".") -> None:
        if isinstance(workspace, UserWorkspace):
            self._user_workspace = workspace
            self._static_workspace = None
        else:
            self._user_workspace = None
            self._static_workspace = Path(workspace)

    def _resolve_skills_dir(self) -> Path:
        if self._user_workspace:
            return self._user_workspace.resolve() / "skills"
        return self._static_workspace / "skills"

    def discover(self) -> list[Skill]:
        """Scan skills directory and load all SKILL.md files."""
        skills_dir = self._resolve_skills_dir()
        if not skills_dir.exists():
            return []

        skills = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill = self._parse_skill(skill_file)
                if skill:
                    skills.append(skill)
        return skills

    def load_always_on(self) -> list[str]:
        """Return names of skills marked as always_on."""
        return [s.name for s in self.discover() if s.always_on]

    def load_skill_body(self, name: str) -> str:
        """Load the body of a specific skill by name."""
        for skill in self.discover():
            if skill.name == name:
                return skill.body
        return ""

    def _parse_skill(self, path: Path) -> Skill | None:
        """Parse a SKILL.md file with YAML frontmatter."""
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not match:
            return None

        frontmatter_str = match.group(1)
        body = match.group(2).strip()

        # Simple YAML parsing (no pyyaml dependency for frontmatter)
        meta = {}
        for line in frontmatter_str.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if val.lower() == "true":
                    meta[key] = True
                elif val.lower() == "false":
                    meta[key] = False
                else:
                    meta[key] = val.strip('"').strip("'")

        return Skill(
            name=meta.get("name", path.parent.name),
            description=meta.get("description", ""),
            always_on=meta.get("always_on", False),
            body=body,
        )
