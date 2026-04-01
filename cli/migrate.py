# -*- coding: utf-8 -*-
"""Claude Code config migration tool.

Reads existing Claude Code configurations (~/.claude/) and converts them
to CodeAgent format (~/.config/codeagent/ and .agent/).
"""
import json
import re
import shutil
from pathlib import Path
from typing import Any


def migrate_from_claude_code(
    source_dir: str | None = None,
    target_dir: str | None = None,
) -> dict[str, Any]:
    """Main migration function — reads Claude Code configs and writes CodeAgent configs.

    Args:
        source_dir: Project directory containing .claude/ (defaults to cwd).
        target_dir: Project directory for .agent/ output (defaults to cwd).

    Returns:
        Dict with stats: {settings_migrated, skills_migrated, hooks_migrated, warnings}.
    """
    source_dir = Path(source_dir) if source_dir else Path.cwd()
    target_dir = Path(target_dir) if target_dir else Path.cwd()
    home = Path.home()

    stats: dict[str, Any] = {
        "settings_migrated": 0,
        "skills_migrated": 0,
        "hooks_migrated": 0,
        "warnings": [],
    }

    # --- 1. Global settings: ~/.claude/settings.json → ~/.config/codeagent/settings.json ---
    global_src = home / ".claude" / "settings.json"
    global_dst = home / ".config" / "codeagent" / "settings.json"
    if global_src.exists():
        try:
            claude_settings = json.loads(global_src.read_text(encoding="utf-8"))
            converted = _convert_settings(claude_settings)
            global_dst.parent.mkdir(parents=True, exist_ok=True)
            global_dst.write_text(
                json.dumps(converted, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            stats["settings_migrated"] += 1
            stats["hooks_migrated"] += len(converted.get("hooks", []))
        except Exception as exc:
            stats["warnings"].append(f"Failed to migrate global settings: {exc}")

    # Also try local overrides
    local_override_src = home / ".claude" / "settings.local.json"
    if local_override_src.exists():
        try:
            local_settings = json.loads(local_override_src.read_text(encoding="utf-8"))
            converted_local = _convert_settings(local_settings)
            local_dst = home / ".config" / "codeagent" / "settings.local.json"
            local_dst.write_text(
                json.dumps(converted_local, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            stats["settings_migrated"] += 1
        except Exception as exc:
            stats["warnings"].append(f"Failed to migrate local overrides: {exc}")

    # --- 2. Project settings: .claude/settings.json → .agent/settings.json ---
    proj_src = source_dir / ".claude" / "settings.json"
    proj_dst = target_dir / ".agent" / "settings.json"
    if proj_src.exists():
        try:
            proj_settings = json.loads(proj_src.read_text(encoding="utf-8"))
            converted_proj = _convert_settings(proj_settings)
            proj_dst.parent.mkdir(parents=True, exist_ok=True)
            proj_dst.write_text(
                json.dumps(converted_proj, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            stats["settings_migrated"] += 1
            stats["hooks_migrated"] += len(converted_proj.get("hooks", []))
        except Exception as exc:
            stats["warnings"].append(f"Failed to migrate project settings: {exc}")

    # --- 3. Global commands: ~/.claude/commands/*.md → ~/.config/codeagent/skills/ ---
    global_cmds = home / ".claude" / "commands"
    global_skills_dst = home / ".config" / "codeagent" / "skills"
    if global_cmds.is_dir():
        stats["skills_migrated"] += _migrate_commands(
            global_cmds, global_skills_dst, stats
        )

    # --- 4. Project commands: .claude/commands/*.md → .agent/skills/ ---
    proj_cmds = source_dir / ".claude" / "commands"
    proj_skills_dst = target_dir / ".agent" / "skills"
    if proj_cmds.is_dir():
        stats["skills_migrated"] += _migrate_commands(
            proj_cmds, proj_skills_dst, stats
        )

    return stats


def _migrate_commands(
    src_dir: Path, dst_dir: Path, stats: dict[str, Any]
) -> int:
    """Copy and convert command .md files from src_dir to dst_dir.

    Returns:
        Number of skills migrated.
    """
    count = 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    for md_file in sorted(src_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            converted = _convert_command_to_skill(content, md_file.name)
            (dst_dir / md_file.name).write_text(converted, encoding="utf-8")
            count += 1
        except Exception as exc:
            stats["warnings"].append(
                f"Failed to migrate command {md_file.name}: {exc}"
            )
    return count


def _convert_settings(claude_settings: dict[str, Any]) -> dict[str, Any]:
    """Convert Claude Code settings dict to CodeAgent format.

    Mapping:
        apiProvider      → model.provider
        model            → model.model_name
        customApiUrl     → model.base_url
        permissions      → permissions.{allow_rules, deny_rules, mode}
        hooks            → hooks list
        permissionMode   → permissions.mode
    """
    result: dict[str, Any] = {}

    # --- Model config ---
    model: dict[str, Any] = {}
    if "apiProvider" in claude_settings:
        model["provider"] = claude_settings["apiProvider"]
    if "model" in claude_settings:
        model["model_name"] = claude_settings["model"]
    if "customApiUrl" in claude_settings:
        model["base_url"] = claude_settings["customApiUrl"]
    if model:
        result["model"] = model

    # --- Permissions ---
    permissions: dict[str, Any] = {}
    if "permissionMode" in claude_settings:
        permissions["mode"] = claude_settings["permissionMode"]

    claude_perms = claude_settings.get("permissions", {})
    if "allow" in claude_perms:
        permissions["allow_rules"] = [
            _parse_permission_rule(rule) for rule in claude_perms["allow"]
        ]
    if "deny" in claude_perms:
        permissions["deny_rules"] = [
            _parse_permission_rule(rule) for rule in claude_perms["deny"]
        ]
    if permissions:
        result["permissions"] = permissions

    # --- Hooks ---
    claude_hooks = claude_settings.get("hooks", {})
    hooks_list: list[dict[str, Any]] = []
    for event_name, hook_entries in claude_hooks.items():
        if not isinstance(hook_entries, list):
            continue
        for entry in hook_entries:
            hook: dict[str, Any] = {
                "event": event_name,
                "type": entry.get("type", "command"),
            }
            if "command" in entry:
                hook["command"] = entry["command"]
            if "if" in entry:
                hook["condition"] = entry["if"]
            if "timeout" in entry:
                hook["timeout"] = entry["timeout"]
            hooks_list.append(hook)
    if hooks_list:
        result["hooks"] = hooks_list

    return result


def _parse_permission_rule(rule: str) -> dict[str, str]:
    """Parse a Claude Code permission rule like 'Bash(git *)' into {tool, pattern}.

    Args:
        rule: Permission string, e.g. 'Bash(git *)', 'Read', 'Write(src/**)'.

    Returns:
        Dict with 'tool' and optionally 'pattern' keys.
    """
    match = re.match(r"^(\w+)\((.+)\)$", rule)
    if match:
        return {"tool": match.group(1), "pattern": match.group(2)}
    return {"tool": rule, "pattern": "*"}


def _convert_command_to_skill(md_content: str, filename: str) -> str:
    """Convert a Claude Code command .md file to CodeAgent skill .md format.

    Parses YAML frontmatter, adds `name` field derived from filename,
    and adds `whenToUse` from description if not already present.

    Args:
        md_content: Raw markdown content of the command file.
        filename: The original filename (e.g. 'run-tests.md').

    Returns:
        Converted markdown string with updated frontmatter.
    """
    name = filename.removesuffix(".md")

    # Split frontmatter and body
    frontmatter, body = _split_frontmatter(md_content)

    # Add/update fields
    if frontmatter is not None:
        frontmatter["name"] = name
        # Add whenToUse from description if not present
        if "whenToUse" not in frontmatter and "description" in frontmatter:
            frontmatter["whenToUse"] = frontmatter["description"]
    else:
        frontmatter = {
            "name": name,
            "description": f"Migrated from Claude Code command: {name}",
            "whenToUse": f"Migrated from Claude Code command: {name}",
        }

    # Rebuild markdown
    fm_lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}:")
            for item in value:
                fm_lines.append(f"  - {json.dumps(item) if not isinstance(item, str) else item}")
        elif isinstance(value, str):
            fm_lines.append(f'{key}: "{value}"')
        else:
            fm_lines.append(f"{key}: {json.dumps(value)}")
    fm_lines.append("---")

    return "\n".join(fm_lines) + "\n" + body


def _split_frontmatter(md_content: str) -> tuple[dict[str, Any] | None, str]:
    """Split markdown into (frontmatter_dict, body_text).

    Uses simple YAML-like parsing (stdlib only — no PyYAML required at runtime).
    """
    stripped = md_content.strip()
    if not stripped.startswith("---"):
        return None, md_content

    # Find closing ---
    end_idx = stripped.find("---", 3)
    if end_idx == -1:
        return None, md_content

    fm_text = stripped[3:end_idx].strip()
    body = stripped[end_idx + 3:].strip()
    if body:
        body = body + "\n"

    # Simple YAML-like parser for flat key-value pairs
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in fm_text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for list item under a key
        if line_stripped.startswith("- ") and current_key is not None and current_list is not None:
            item = line_stripped[2:].strip().strip('"').strip("'")
            current_list.append(item)
            result[current_key] = current_list
            continue

        # Key-value pair
        if ":" in line_stripped:
            key, _, val = line_stripped.partition(":")
            key = key.strip()
            val = val.strip()

            if not val:
                # Might be a list
                current_key = key
                current_list = []
                result[key] = current_list
            else:
                # Scalar value — strip quotes
                val = val.strip('"').strip("'")
                result[key] = val
                current_key = None
                current_list = None

    return result, body
