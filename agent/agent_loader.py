# -*- coding: utf-8 -*-
"""Agent definition loader - loads sub-agent definitions from .agent/agents/.

Implements Unit 11 from the plan.
Follows the same pattern as skills/loader.py.
"""
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.frontmatter import load_frontmatter_file


@dataclass
class AgentDefinition:
    """A loaded agent definition from a .md file.

    Compatible with both codeagent and oh-my-claudecode agent formats.
    """

    name: str
    description: str = ""
    tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    prompt: str = ""  # Main body / system prompt
    source_path: str | None = None

    # Alias for backward compat
    @property
    def system_prompt(self) -> str:
        return self.prompt


class AgentDefinitionLoader:
    """Loads agent definitions from multiple directories.

    Search order (later wins on name collision):
    1. Bundled agents shipped with codeagent  (codeagent/agents/)
    2. User agents                            (~/.config/codeagent/agents/)
    3. Project agents                         (.agent/agents/)

    Each .md file defines a sub-agent via YAML frontmatter
    (name, description, model, disallowedTools, etc.).
    The Markdown body becomes the agent's system prompt.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, AgentDefinition] = {}

    def load_all(self, project_root: str | None = None) -> list[AgentDefinition]:
        """Load agent definitions from all directories.

        Args:
            project_root: Project root directory. Defaults to cwd.

        Returns:
            List of loaded AgentDefinition instances.
        """
        self._definitions.clear()

        # 1. Bundled agents (shipped with package)
        bundled_dir = Path(__file__).parent.parent / "agents"
        self._load_directory(bundled_dir)

        # 2. User agents
        user_dir = Path.home() / ".config" / "codeagent" / "agents"
        self._load_directory(user_dir)

        # 3. Project agents (highest priority — overwrites)
        root = Path(project_root) if project_root else Path.cwd()
        self._load_directory(root / ".agent" / "agents")
        self._load_directory(root / ".codeagent" / "agents")

        return list(self._definitions.values())

    def _load_directory(self, agents_dir: Path) -> None:
        """Load all .md agent definitions from a directory."""
        if not agents_dir.exists() or not agents_dir.is_dir():
            return

        for fpath in sorted(agents_dir.glob("*.md")):
            try:
                definition = self._parse_agent_file(fpath)
                if definition:
                    self._definitions[definition.name] = definition
            except Exception as e:
                warnings.warn(
                    f"Failed to load agent definition from {fpath}: {e}",
                    stacklevel=2,
                )

    def get_definition(self, name: str) -> AgentDefinition | None:
        """Get a single agent definition by name.

        If definitions haven't been loaded yet, auto-loads them.

        Args:
            name: The agent name to look up.

        Returns:
            AgentDefinition if found, None otherwise.
        """
        if not self._definitions:
            self.load_all()
        return self._definitions.get(name)

    def _parse_agent_file(self, path: Path) -> AgentDefinition | None:
        """Parse a single agent definition Markdown file.

        Compatible with both codeagent format and OMC format:
        - codeagent: tools, system_prompt in frontmatter
        - OMC: disallowedTools in frontmatter, body is the prompt

        Args:
            path: Path to the .md file.

        Returns:
            AgentDefinition or None if the file is invalid.
        """
        doc = load_frontmatter_file(str(path))
        meta = doc.metadata

        name = meta.get("name", path.stem)
        if not name:
            return None

        # The body serves as the prompt unless overridden in frontmatter
        prompt = meta.get("system_prompt", doc.body)

        # Handle OMC's disallowedTools (comma-separated string or list)
        disallowed_raw = meta.get("disallowedTools", meta.get("disallowed_tools", []))
        if isinstance(disallowed_raw, str):
            disallowed = [t.strip() for t in disallowed_raw.split(",") if t.strip()]
        else:
            disallowed = disallowed_raw or []

        # Handle tools list
        tools_raw = meta.get("tools", [])
        if isinstance(tools_raw, str):
            tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
        else:
            tools = tools_raw or []

        return AgentDefinition(
            name=name,
            description=meta.get("description", ""),
            tools=tools,
            disallowed_tools=disallowed,
            model=meta.get("model"),
            prompt=prompt,
            source_path=str(path),
        )
