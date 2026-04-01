# -*- coding: utf-8 -*-
"""Interactive setup wizard for CodeAgent.

Usage:
    python -m codeagent setup
    python -m codeagent setup --non-interactive --provider anthropic --model claude-opus-4-6
"""
import json
import os
import sys
from pathlib import Path


_PROVIDERS = {
    "openai": {
        "default_model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"],
    },
    "anthropic": {
        "default_model": "claude-opus-4-6",
        "env_key": "ANTHROPIC_API_KEY",
        "models": [
            "claude-opus-4-6", "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
        ],
    },
    "dashscope": {
        "default_model": "qwen-max",
        "env_key": "DASHSCOPE_API_KEY",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
    },
    "gemini": {
        "default_model": "gemini-2.0-flash",
        "env_key": "GOOGLE_API_KEY",
        "models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-pro"],
    },
    "ollama": {
        "default_model": "llama3.1",
        "env_key": None,
        "models": ["llama3.1", "codellama", "deepseek-coder", "qwen2.5-coder"],
    },
}


def setup_codeagent(
    non_interactive: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Run the interactive setup wizard.

    Args:
        non_interactive: Skip prompts, use defaults/provided values.
        provider: Pre-selected provider.
        model: Pre-selected model.
    """
    print()
    print("🤖 CodeAgent Setup Wizard")
    print("=" * 40)
    print()

    # 1. Check dependencies
    _check_dependencies()

    # 2. Select provider
    if not provider:
        if non_interactive:
            provider = "openai"
        else:
            provider = _prompt_provider()

    # 3. Select model
    if not model:
        if non_interactive:
            model = _PROVIDERS[provider]["default_model"]
        else:
            model = _prompt_model(provider)

    # 4. API key
    env_key = _PROVIDERS.get(provider, {}).get("env_key")
    api_key = None
    base_url = None

    if env_key and not non_interactive:
        existing = os.environ.get(env_key, "")
        if existing:
            print(f"  ✅ {env_key} found in environment")
        else:
            api_key = input(f"  Enter {env_key} (or press Enter to skip): ").strip()
            if not api_key:
                api_key = None

        base_url_input = input("  Custom API base URL (or press Enter for default): ").strip()
        if base_url_input:
            base_url = base_url_input

    # 5. Permission mode
    if non_interactive:
        perm_mode = "default"
    else:
        perm_mode = _prompt_permission_mode()

    # 6. Build config
    config = {
        "model": {
            "provider": provider,
            "model_name": model,
            "stream": True,
        },
        "permissions": {
            "mode": perm_mode,
        },
    }
    if api_key:
        config["model"]["api_key"] = api_key
    if base_url:
        config["model"]["base_url"] = base_url

    # 7. Write global config
    global_dir = Path.home() / ".config" / "codeagent"
    global_dir.mkdir(parents=True, exist_ok=True)
    global_config_path = global_dir / "settings.json"

    if global_config_path.exists() and not non_interactive:
        overwrite = input(
            f"  {global_config_path} exists. Overwrite? [y/N]: "
        ).strip().lower()
        if overwrite != "y":
            print("  Skipped global config.")
        else:
            _write_json(global_config_path, config)
            print(f"  ✅ Global config: {global_config_path}")
    else:
        _write_json(global_config_path, config)
        print(f"  ✅ Global config: {global_config_path}")

    # 8. Create project .agent/ structure
    if not non_interactive:
        create_project = input("\n  Create .agent/ in current directory? [Y/n]: ").strip().lower()
    else:
        create_project = "y"

    if create_project != "n":
        _create_project_structure()

    # 9. Offer Claude Code migration
    claude_dir = Path.home() / ".claude"
    if claude_dir.exists() and not non_interactive:
        migrate = input(
            "\n  📦 Detected Claude Code config (~/.claude/). Migrate? [Y/n]: "
        ).strip().lower()
        if migrate != "n":
            from .migrate import migrate_from_claude_code
            result = migrate_from_claude_code()
            print(f"  Migrated: {result.get('settings_migrated', 0)} settings, "
                  f"{result.get('skills_migrated', 0)} skills, "
                  f"{result.get('hooks_migrated', 0)} hooks")

    # 10. Done
    print()
    print("=" * 40)
    print("🎉 Setup complete!")
    print()
    print("  Start CodeAgent:")
    print(f"    python -m codeagent")
    print(f"    python -m codeagent --model {model} --provider {provider}")
    print()
    print("  With AgentScope Studio:")
    print(f"    python -m codeagent --studio auto")
    print()
    print("  With A2A protocol:")
    print(f"    python -m codeagent --a2a")
    print()


def _check_dependencies() -> None:
    """Check required dependencies."""
    print("📦 Checking dependencies...")
    deps = [
        ("agentscope", "agentscope"),
        ("pydantic", "pydantic"),
        ("rich", "rich"),
        ("prompt_toolkit", "prompt-toolkit"),
    ]
    missing = []
    for import_name, pip_name in deps:
        try:
            __import__(import_name)
            print(f"  ✅ {pip_name}")
        except ImportError:
            print(f"  ❌ {pip_name}")
            missing.append(pip_name)

    if missing:
        print(f"\n  Missing: pip install {' '.join(missing)}")
    print()


def _prompt_provider() -> str:
    """Prompt user to select a model provider."""
    print("🔧 Select model provider:")
    providers = list(_PROVIDERS.keys())
    for i, p in enumerate(providers, 1):
        env = _PROVIDERS[p].get("env_key", "none")
        mark = " ✅" if env and os.environ.get(env) else ""
        print(f"  {i}. {p} (env: {env or 'N/A'}){mark}")

    while True:
        choice = input(f"\n  Choose [1-{len(providers)}] (default: 1): ").strip()
        if not choice:
            return providers[0]
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                return providers[idx]
        except ValueError:
            if choice in providers:
                return choice
        print("  Invalid choice, try again.")


def _prompt_model(provider: str) -> str:
    """Prompt user to select a model."""
    models = _PROVIDERS.get(provider, {}).get("models", [])
    default = _PROVIDERS.get(provider, {}).get("default_model", "")
    print(f"\n🧠 Select model ({provider}):")
    for i, m in enumerate(models, 1):
        default_mark = " (default)" if m == default else ""
        print(f"  {i}. {m}{default_mark}")
    print(f"  Or type a custom model name")

    choice = input(f"\n  Choose [1-{len(models)}] or name (default: {default}): ").strip()
    if not choice:
        return default
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            return models[idx]
    except ValueError:
        pass
    return choice  # Custom model name


def _prompt_permission_mode() -> str:
    """Prompt user to select permission mode."""
    print("\n🔒 Permission mode:")
    print("  1. default — Ask for each tool call")
    print("  2. acceptEdits — Auto-approve file operations")
    print("  3. bypassPermissions — Auto-approve everything")

    choice = input("\n  Choose [1-3] (default: 1): ").strip()
    modes = {"1": "default", "2": "acceptEdits", "3": "bypassPermissions"}
    return modes.get(choice, "default")


def _create_project_structure() -> None:
    """Create .agent/ directory structure in the current directory."""
    dirs = [
        ".agent",
        ".agent/skills",
        ".agent/agents",
        ".agent/plans",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Create default settings.json if not exists
    settings_path = Path(".agent/settings.json")
    if not settings_path.exists():
        _write_json(settings_path, {
            "model": {},
            "permissions": {"mode": "default"},
        })

    # Create AGENT.md if not exists
    agent_md = Path("AGENT.md")
    if not agent_md.exists():
        agent_md.write_text(
            "# Project Memory\n\n"
            "<!-- Add project-specific instructions for CodeAgent here -->\n",
            encoding="utf-8",
        )

    print("  ✅ Created .agent/ directory structure")
    print("  ✅ Created AGENT.md")


def _write_json(path: Path, data: dict) -> None:
    """Write a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# Slash command handlers (async, for CommandRegistry)
# ---------------------------------------------------------------------------

async def cmd_setup(args: str, ctx: dict) -> str:
    """Slash command handler for /setup.

    Runs setup in non-interactive mode and returns a summary.
    """
    try:
        setup_codeagent(non_interactive=True, provider="anthropic")
        config_path = Path.home() / ".config" / "codeagent" / "settings.json"
        lines = [
            "# Setup Complete",
            f"- Config: `{config_path}`",
            f"- Project dir: `{Path.cwd() / '.agent'}`",
        ]
        return "\n".join(lines)
    except Exception as exc:
        return f"Setup failed: {exc}"


async def cmd_migrate(args: str, ctx: dict) -> str:
    """Slash command handler for /migrate.

    Runs Claude Code config migration and returns a summary.
    """
    from .migrate import migrate_from_claude_code

    try:
        stats = migrate_from_claude_code()
        lines = [
            "# Claude Code Migration Complete",
            f"- Settings migrated: **{stats['settings_migrated']}**",
            f"- Skills migrated: **{stats['skills_migrated']}**",
            f"- Hooks migrated: **{stats['hooks_migrated']}**",
        ]
        if stats["warnings"]:
            lines.append("\n## Warnings")
            for w in stats["warnings"]:
                lines.append(f"- ⚠ {w}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Migration failed: {exc}"
