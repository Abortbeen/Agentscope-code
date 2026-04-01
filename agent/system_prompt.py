# -*- coding: utf-8 -*-
"""System prompt builder for the coding agent.

Collects project context (git info, project memory, tool list, permissions)
and assembles a comprehensive system prompt.
"""
import os
from pathlib import Path

from ..config.schema import PermissionsConfig
from ..utils.git import GitInfo


_BASE_SYSTEM_PROMPT = """\
You are an expert AI coding assistant running in a terminal. You help users \
understand, write, debug, and improve code. You have access to tools for \
reading/writing files, executing shell commands, searching code, and more.

# Core Principles
- Be concise but thorough
- Always read files before editing them
- Prefer editing existing files over creating new ones
- Run tests after making changes
- Never commit sensitive files (.env, credentials, keys)
- Ask the user when uncertain about destructive operations

# Tool Usage
- Use Bash for shell commands (with timeout awareness)
- Use FileRead/FileWrite/FileEdit for file operations
- Use GlobSearch for finding files by pattern
- Use GrepSearch for searching file contents
- Use WebSearch/WebFetch for internet queries
"""


class SystemPromptBuilder:
    """Builds the system prompt by collecting project context."""

    def __init__(
        self,
        permissions_config: PermissionsConfig | None = None,
    ) -> None:
        self._permissions_config = permissions_config

    def build(
        self,
        git_info: GitInfo | None = None,
        project_memory: str | None = None,
        tool_names: list[str] | None = None,
        extra_context: str | None = None,
    ) -> str:
        """Build the complete system prompt.

        Args:
            git_info: Git repository information.
            project_memory: Content from AGENT.md / CLAUDE.md files.
            tool_names: List of available tool names.
            extra_context: Additional context to append.

        Returns:
            The assembled system prompt string.
        """
        parts = [_BASE_SYSTEM_PROMPT]

        # Project structure
        cwd = os.getcwd()
        parts.append(f"\n# Working Directory\n{cwd}\n")

        # Git info
        if git_info and git_info.is_repo:
            git_section = "\n# Git Repository\n"
            git_section += f"- Root: {git_info.root}\n"
            if git_info.branch:
                git_section += f"- Branch: {git_info.branch}\n"
            if git_info.remote_url:
                git_section += f"- Remote: {git_info.remote_url}\n"
            if git_info.status:
                git_section += f"- Status:\n```\n{git_info.status}\n```\n"
            parts.append(git_section)

        # Project memory (AGENT.md)
        if project_memory:
            parts.append(
                f"\n# Project Memory\n"
                f"<project-memory>\n{project_memory}\n</project-memory>\n"
            )

        # Available tools
        if tool_names:
            tools_section = "\n# Available Tools\n"
            tools_section += ", ".join(tool_names) + "\n"
            parts.append(tools_section)

        # Permission mode
        if self._permissions_config:
            mode = self._permissions_config.mode
            parts.append(f"\n# Permission Mode: {mode}\n")

        # Available agents
        agents_summary = self._load_agents_summary()
        if agents_summary:
            parts.append(agents_summary)

        # Extra context
        if extra_context:
            parts.append(f"\n{extra_context}\n")

        return "\n".join(parts)

    @staticmethod
    def _load_agents_summary() -> str:
        """Load summary of available agent definitions for the system prompt."""
        try:
            from .agent_loader import AgentDefinitionLoader
            loader = AgentDefinitionLoader()
            definitions = loader.load_all()
            if not definitions:
                return ""
            lines = ["\n# Available Agent Types",
                     "Use SpawnAgent with agent_type to delegate to these specialists:\n"]
            for d in sorted(definitions, key=lambda x: x.name):
                model_hint = f" (model: {d.model})" if d.model else ""
                lines.append(f"- **{d.name}**{model_hint}: {d.description}")
            return "\n".join(lines) + "\n"
        except Exception:
            return ""

    @staticmethod
    def load_project_memory(start_path: str | None = None) -> str | None:
        """Load and merge project memory files (AGENT.md / CLAUDE.md).

        Walks up from start_path, collecting memory files at each level.
        Also checks global config directory.

        Returns:
            Merged memory content, or None if no files found.
        """
        start = Path(start_path) if start_path else Path.cwd()
        memory_parts: list[str] = []
        filenames = ["AGENT.md", "CLAUDE.md"]

        # Check global config
        global_dir = Path.home() / ".config" / "codeagent"
        for fname in filenames:
            global_file = global_dir / fname
            if global_file.exists():
                try:
                    content = global_file.read_text(encoding="utf-8").strip()
                    if content:
                        memory_parts.append(
                            f"<!-- Global: {global_file} -->\n{content}"
                        )
                except OSError:
                    pass
                break  # Only load first found

        # Walk up from start_path to root, collecting memory files
        collected: list[tuple[Path, str]] = []
        current = start.resolve()
        for directory in [current, *current.parents]:
            for fname in filenames:
                fpath = directory / fname
                if fpath.exists():
                    try:
                        content = fpath.read_text(encoding="utf-8").strip()
                        if content:
                            collected.append((fpath, content))
                    except OSError:
                        pass
                    break  # Only first found per directory

        # Add in root-to-leaf order
        for fpath, content in reversed(collected):
            memory_parts.append(f"<!-- {fpath} -->\n{content}")

        return "\n\n".join(memory_parts) if memory_parts else None
