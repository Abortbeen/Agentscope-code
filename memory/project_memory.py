# -*- coding: utf-8 -*-
"""Project memory loading - AGENT.md / CLAUDE.md hierarchical loading.

Implements R32-R33 from the plan.
"""
from pathlib import Path


def load_project_memory(
    start_path: str | None = None,
    memory_filename: str = "AGENT.md",
) -> str | None:
    """Load and merge project memory files hierarchically.

    Searches for memory files (AGENT.md, with CLAUDE.md as fallback)
    from the global config dir through the project root to the current directory.

    Args:
        start_path: Starting directory. Defaults to cwd.
        memory_filename: Primary memory filename.

    Returns:
        Merged memory content, or None if no files found.
    """
    start = Path(start_path) if start_path else Path.cwd()
    filenames = [memory_filename, "CLAUDE.md"]
    memory_parts: list[str] = []

    # Global config
    global_dir = Path.home() / ".config" / "codeagent"
    for fname in filenames:
        gpath = global_dir / fname
        if gpath.exists():
            try:
                content = gpath.read_text(encoding="utf-8").strip()
                if content:
                    memory_parts.append(f"<!-- Global: {gpath} -->\n{content}")
            except OSError:
                pass
            break

    # Walk up from start_path
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
                break

    # Root-to-leaf order
    for fpath, content in reversed(collected):
        memory_parts.append(f"<!-- {fpath} -->\n{content}")

    return "\n\n".join(memory_parts) if memory_parts else None
