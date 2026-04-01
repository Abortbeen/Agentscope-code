# -*- coding: utf-8 -*-
"""Skill registry - manages loaded skills.

Implements R20-R23 from the plan.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Skill:
    """A loaded skill definition."""
    name: str
    description: str = ""
    when_to_use: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    prompt: str = ""
    source_path: str | None = None
    priority: int = 0  # Higher = more priority (project > user > bundled)


class SkillRegistry:
    """Registry for skills with priority-based deduplication."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill. Higher priority wins on name collision."""
        existing = self._skills.get(skill.name)
        if existing is None or skill.priority > existing.priority:
            self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        """List all registered skills."""
        return sorted(self._skills.values(), key=lambda s: s.name)

    def get_skill_prompt(self, name: str) -> str | None:
        """Get the prompt content of a skill."""
        skill = self._skills.get(name)
        return skill.prompt if skill else None

    def get_skills_summary(self) -> str:
        """Generate a summary of available skills for the system prompt."""
        if not self._skills:
            return ""

        lines = ["# Available Skills"]
        for skill in self.list_skills():
            lines.append(f"- **{skill.name}**: {skill.description}")
            if skill.when_to_use:
                lines.append(f"  When: {skill.when_to_use}")
        return "\n".join(lines)

    def remove(self, name: str) -> bool:
        """Remove a skill by name."""
        return self._skills.pop(name, None) is not None

    def clear(self) -> None:
        """Remove all skills."""
        self._skills.clear()
