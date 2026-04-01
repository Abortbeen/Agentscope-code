# -*- coding: utf-8 -*-
"""Slash command system for the REPL.

Supports built-in commands like /help, /clear, /compact, /model, /exit.
"""
from typing import Callable, Awaitable, Any

from .renderer import console, render_info, render_markdown


class CommandRegistry:
    """Registry of slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, dict[str, Any]] = {}
        self._register_builtins()

    def register(
        self,
        name: str,
        handler: Callable[..., Awaitable[str | None]],
        description: str = "",
        usage: str = "",
    ) -> None:
        """Register a slash command."""
        self._commands[name] = {
            "handler": handler,
            "description": description,
            "usage": usage,
        }

    def is_command(self, text: str) -> bool:
        """Check if input text is a slash command."""
        return text.strip().startswith("/")

    async def execute(self, text: str, context: dict | None = None) -> str | None:
        """Execute a slash command.

        Args:
            text: The full command text (e.g., '/model gpt-4o').
            context: Optional context dict with agent/config references.

        Returns:
            Response text or None.
        """
        parts = text.strip().split(maxsplit=1)
        cmd_name = parts[0].lstrip("/")
        args = parts[1] if len(parts) > 1 else ""

        if cmd_name not in self._commands:
            return f"Unknown command: /{cmd_name}. Type /help for available commands."

        handler = self._commands[cmd_name]["handler"]
        return await handler(args, context or {})

    def _register_builtins(self) -> None:
        """Register built-in commands."""
        self.register("help", self._cmd_help, "Show available commands")
        self.register("clear", self._cmd_clear, "Clear the screen")
        self.register("exit", self._cmd_exit, "Exit CodeAgent")
        self.register("quit", self._cmd_exit, "Exit CodeAgent")
        self.register("model", self._cmd_model, "Show or switch model", "/model [model_name]")
        self.register("compact", self._cmd_compact, "Compress conversation memory")
        self.register("version", self._cmd_version, "Show version")
        self.register("config", self._cmd_config, "Show current config")
        self.register("remember", self._cmd_remember, "Save note to project memory", "/remember <text>")

        # Deploy / migration commands
        from .deploy import cmd_setup, cmd_migrate
        self.register("setup", cmd_setup, "Run interactive setup wizard")
        self.register("migrate", cmd_migrate, "Migrate Claude Code config to CodeAgent")

    async def _cmd_help(self, args: str, ctx: dict) -> str:
        """Show help text."""
        lines = ["# Available Commands\n"]
        for name, info in sorted(self._commands.items()):
            usage = f" `{info['usage']}`" if info.get("usage") else ""
            lines.append(f"- **/{name}**{usage} — {info['description']}")
        return "\n".join(lines)

    async def _cmd_clear(self, args: str, ctx: dict) -> str | None:
        """Clear screen."""
        console.clear()
        return None

    async def _cmd_exit(self, args: str, ctx: dict) -> str:
        """Signal exit."""
        raise SystemExit(0)

    async def _cmd_model(self, args: str, ctx: dict) -> str:
        """Show or switch model."""
        if not args:
            config = ctx.get("config")
            if config:
                return f"Current model: **{config.model.model_name}** ({config.model.provider})"
            return "No config available."

        # Model switching would require reinitializing the agent
        return f"Model switching to **{args}** — restart required for now."

    async def _cmd_compact(self, args: str, ctx: dict) -> str:
        """Trigger memory compression."""
        agent = ctx.get("agent")
        if agent:
            return "Memory compression triggered. (Implementation pending)"
        return "No active agent."

    async def _cmd_version(self, args: str, ctx: dict) -> str:
        """Show version."""
        from codeagent import __version__
        return f"CodeAgent v{__version__}"

    async def _cmd_config(self, args: str, ctx: dict) -> str:
        """Show current config."""
        config = ctx.get("config")
        if config:
            import json
            return f"```json\n{json.dumps(config.model_dump(), indent=2, default=str)}\n```"
        return "No config available."

    async def _cmd_remember(self, args: str, ctx: dict) -> str:
        """Save a note to project memory."""
        if not args:
            return "Usage: /remember <text to remember>"

        from ..memory.remember import append_to_memory
        success = append_to_memory(args)
        if success:
            return f"✓ Saved to project memory: {args}"
        return "Failed to save to project memory."
