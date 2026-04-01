# -*- coding: utf-8 -*-
"""Entry point for python -m codeagent.

Supports subcommands:
  python -m codeagent                    — Start REPL
  python -m codeagent setup              — Interactive setup wizard
  python -m codeagent migrate            — Migrate from Claude Code
  python -m codeagent --version          — Show version
  python -m codeagent "fix the bug"      — Non-interactive mode
"""
# Suppress agentscope studio/tracing warnings BEFORE any imports
import logging as _logging
_logging.getLogger("agentscope").setLevel(_logging.ERROR)

import argparse
import asyncio
import sys

from . import __version__


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="codeagent",
        description="An open-source AI coding agent built on AgentScope",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"codeagent {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- 'run' is the default (REPL) ---
    run_parser = subparsers.add_parser("run", help="Start the REPL (default)")
    _add_run_args(run_parser)

    # --- 'setup' command ---
    setup_parser = subparsers.add_parser(
        "setup", help="Interactive setup wizard",
    )
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run setup with defaults (no prompts)",
    )
    setup_parser.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=["openai", "anthropic", "dashscope", "gemini", "ollama"],
        help="Model provider",
    )
    setup_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name",
    )

    # --- 'migrate' command ---
    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate configuration from Claude Code",
    )
    migrate_parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Claude Code config directory (default: ~/.claude)",
    )
    migrate_parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Target config directory (default: ~/.config/codeagent)",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing",
    )
    migrate_parser.add_argument(
        "--project",
        action="store_true",
        help="Also migrate project-level .claude/ to .agent/",
    )

    return parser


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    """Add REPL-related arguments to a parser."""
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (e.g., gpt-4o, claude-opus-4-6, qwen-max)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=["openai", "anthropic", "dashscope", "gemini", "ollama"],
        help="Model provider",
    )
    parser.add_argument(
        "--permission-mode",
        type=str,
        default=None,
        choices=["default", "acceptEdits", "bypassPermissions"],
        help="Permission mode for tool execution",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print merged config and exit",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        nargs="?",
        const="latest",
        help="Resume a previous session (optionally specify session ID)",
    )
    parser.add_argument(
        "--studio",
        type=str,
        default=None,
        nargs="?",
        const="auto",
        help="Connect to AgentScope Studio (URL or 'auto' to launch)",
    )
    parser.add_argument(
        "--studio-port",
        type=int,
        default=7860,
        help="Port for auto-launched Studio (default: 7860)",
    )
    parser.add_argument(
        "--a2a",
        action="store_true",
        help="Enable A2A protocol server",
    )
    parser.add_argument(
        "--a2a-port",
        type=int,
        default=7861,
        help="Port for A2A server (default: 7861)",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Initial prompt (non-interactive mode if provided)",
    )


def _cmd_run(args: argparse.Namespace) -> None:
    """Run the REPL."""
    from .config.settings import load_config
    from .cli.repl import run_repl

    config = load_config()

    # CLI overrides
    if getattr(args, "model", None):
        config.model.model_name = args.model
    if getattr(args, "provider", None):
        config.model.provider = args.provider
    if getattr(args, "permission_mode", None):
        config.permissions.mode = args.permission_mode

    # Studio overrides
    if getattr(args, "studio", None):
        config.studio.enabled = True
        if args.studio == "auto":
            config.studio.auto_launch = True
        else:
            config.studio.url = args.studio
    if getattr(args, "studio_port", None):
        config.studio.port = args.studio_port

    # A2A overrides
    if getattr(args, "a2a", False):
        config.a2a.enabled = True
    if getattr(args, "a2a_port", None):
        config.a2a.port = args.a2a_port

    if getattr(args, "print_config", False):
        import json
        print(json.dumps(config.model_dump(), indent=2, default=str))
        sys.exit(0)

    initial_prompt = " ".join(args.prompt) if getattr(args, "prompt", None) else None
    resume = getattr(args, "resume", None)
    asyncio.run(run_repl(config, initial_prompt=initial_prompt, resume_session=resume))


def _cmd_setup(args: argparse.Namespace) -> None:
    """Run the interactive setup wizard."""
    from .cli.deploy import setup_codeagent
    setup_codeagent(
        non_interactive=getattr(args, "non_interactive", False),
        provider=getattr(args, "provider", None),
        model=getattr(args, "model", None),
    )


def _cmd_migrate(args: argparse.Namespace) -> None:
    """Run Claude Code migration."""
    from .cli.migrate import migrate_from_claude_code

    result = migrate_from_claude_code(
        source_dir=getattr(args, "source", None),
        target_dir=getattr(args, "target", None),
    )

    print("\n📊 Migration Summary:")
    print(f"  Settings migrated: {result.get('settings_migrated', 0)}")
    print(f"  Skills migrated:   {result.get('skills_migrated', 0)}")
    print(f"  Hooks migrated:    {result.get('hooks_migrated', 0)}")
    if result.get("warnings"):
        print("\n⚠️  Warnings:")
        for w in result["warnings"]:
            print(f"  - {w}")
    print("\n✅ Migration complete!")


def main() -> None:
    """Main entry point."""
    parser = _build_parser()

    # If first arg is not a subcommand, treat everything as 'run' mode
    known_commands = {"run", "setup", "migrate"}
    if len(sys.argv) > 1 and sys.argv[1] not in known_commands and not sys.argv[1].startswith("-"):
        # Treat as: run <prompt...>
        sys.argv.insert(1, "run")
    elif len(sys.argv) == 1:
        # No args: default to run
        sys.argv.append("run")

    args = parser.parse_args()

    if args.command == "setup":
        _cmd_setup(args)
    elif args.command == "migrate":
        _cmd_migrate(args)
    else:
        _cmd_run(args)


if __name__ == "__main__":
    main()
