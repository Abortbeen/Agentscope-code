# -*- coding: utf-8 -*-
"""Remember command - append notes to project memory file.

Implements R34 from the plan.
"""
import os
from datetime import datetime
from pathlib import Path


def _find_memory_file(start_path: str | None = None) -> Path:
    """Find or create the project memory file.

    Looks for AGENT.md in the git root or cwd.
    Creates one if it doesn't exist.
    """
    start = Path(start_path) if start_path else Path.cwd()

    # Try to find existing AGENT.md walking up
    for directory in [start, *start.parents]:
        for fname in ["AGENT.md", "CLAUDE.md"]:
            candidate = directory / fname
            if candidate.exists():
                return candidate

        # Stop at git root
        if (directory / ".git").exists():
            return directory / "AGENT.md"

    # Default: create in cwd
    return start / "AGENT.md"


def append_to_memory(
    text: str,
    start_path: str | None = None,
) -> bool:
    """Append a note to the project memory file.

    Args:
        text: The text to remember.
        start_path: Starting directory to search for memory file.

    Returns:
        True if successful.
    """
    try:
        path = _find_memory_file(start_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Read existing content
        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8")

        # Append
        entry = f"\n\n<!-- remembered {timestamp} -->\n- {text}\n"
        with open(path, "a", encoding="utf-8") as f:
            if not existing:
                f.write("# Project Memory\n")
            f.write(entry)

        return True

    except OSError:
        return False
