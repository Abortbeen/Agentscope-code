# -*- coding: utf-8 -*-
"""GlobTool - File pattern search.

Implements R7 from the plan.
"""
import os
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

# Directories to always skip
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".eggs", "*.egg-info",
}


def _should_skip(path: Path) -> bool:
    """Check if a path should be skipped."""
    return any(part in _SKIP_DIRS for part in path.parts)


async def glob_search(
    pattern: str,
    path: str | None = None,
    max_results: int = 250,
) -> ToolResponse:
    """Search for files matching a glob pattern.

    Results are sorted by modification time (most recent first).

    Args:
        pattern: Glob pattern (e.g., '**/*.py', 'src/**/*.ts').
        path: Directory to search in. Defaults to cwd.
        max_results: Maximum number of results to return. Default 250.

    Returns:
        ToolResponse with matching file paths.
    """
    search_dir = Path(path) if path else Path.cwd()

    if not search_dir.is_dir():
        return ToolResponse(
            content=[TextBlock(text=f"Error: Directory does not exist: {search_dir}")],
        )

    try:
        matches = []
        for p in search_dir.glob(pattern):
            if p.is_file() and not _should_skip(p):
                try:
                    mtime = p.stat().st_mtime
                    matches.append((mtime, str(p)))
                except OSError:
                    continue

        # Sort by mtime descending (most recent first)
        matches.sort(key=lambda x: x[0], reverse=True)

        total = len(matches)
        truncated = matches[:max_results]
        paths = [m[1] for m in truncated]

        if not paths:
            return ToolResponse(
                content=[TextBlock(text=f"No files found matching '{pattern}' in {search_dir}")],
            )

        output = "\n".join(paths)
        if total > max_results:
            output += f"\n\n... ({total - max_results} more results truncated)"

        return ToolResponse(
            content=[TextBlock(text=output)],
            metadata={"total": total, "returned": len(paths)},
        )

    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error during glob search: {e}")],
        )
