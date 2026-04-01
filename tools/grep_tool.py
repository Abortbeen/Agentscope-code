# -*- coding: utf-8 -*-
"""GrepTool - Content search using ripgrep with Python fallback.

Implements R8 from the plan.
"""
import asyncio
import os
import re
from pathlib import Path
from typing import Literal

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


# File type to extension mapping (subset of rg --type)
_TYPE_MAP = {
    "py": ["*.py"],
    "js": ["*.js", "*.jsx"],
    "ts": ["*.ts", "*.tsx"],
    "rust": ["*.rs"],
    "go": ["*.go"],
    "java": ["*.java"],
    "c": ["*.c", "*.h"],
    "cpp": ["*.cpp", "*.hpp", "*.cc", "*.cxx"],
    "ruby": ["*.rb"],
    "md": ["*.md"],
    "json": ["*.json"],
    "yaml": ["*.yaml", "*.yml"],
    "html": ["*.html", "*.htm"],
    "css": ["*.css", "*.scss"],
    "sql": ["*.sql"],
    "sh": ["*.sh", "*.bash"],
}


async def _try_ripgrep(
    pattern: str,
    path: str,
    file_type: str | None,
    output_mode: str,
    context: int,
    case_insensitive: bool,
    max_results: int,
) -> tuple[str | None, int]:
    """Try to use ripgrep. Returns (output, count) or (None, 0) if rg not available."""
    cmd_parts = ["rg"]

    if output_mode == "files_with_matches":
        cmd_parts.append("-l")
    elif output_mode == "count":
        cmd_parts.append("-c")
    else:
        cmd_parts.append("-n")  # line numbers

    if case_insensitive:
        cmd_parts.append("-i")

    if context > 0 and output_mode == "content":
        cmd_parts.extend(["-C", str(context)])

    if file_type and file_type in _TYPE_MAP:
        cmd_parts.extend(["--type", file_type])

    cmd_parts.extend([
        "--max-count", str(max_results),
        "--no-heading",
        "--color", "never",
        "--",
        pattern,
        path,
    ])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode == 2:
            # rg error (bad pattern, etc.)
            return f"Regex error: {stderr.decode()}", 0

        output = stdout.decode("utf-8", errors="replace").strip()
        count = len(output.splitlines()) if output else 0
        return output, count

    except FileNotFoundError:
        return None, 0  # rg not installed
    except asyncio.TimeoutError:
        return "Error: Search timed out", 0


async def _python_fallback(
    pattern: str,
    path: str,
    file_type: str | None,
    output_mode: str,
    context: int,
    case_insensitive: bool,
    max_results: int,
) -> tuple[str, int]:
    """Python re-based fallback when ripgrep is not available."""
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Invalid regex pattern: {e}", 0

    # Determine extensions filter
    extensions = None
    if file_type and file_type in _TYPE_MAP:
        extensions = set()
        for glob_pat in _TYPE_MAP[file_type]:
            extensions.add(glob_pat.replace("*", ""))

    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    results = []
    file_matches = set()
    count = 0
    search_path = Path(path)

    for root, dirs, files in os.walk(search_path):
        # Skip hidden/vendor dirs
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

        for fname in files:
            if extensions and not any(fname.endswith(ext) for ext in extensions):
                continue

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except (OSError, UnicodeDecodeError):
                continue

            for lineno, line in enumerate(lines, 1):
                if regex.search(line):
                    count += 1
                    if count > max_results:
                        break

                    if output_mode == "files_with_matches":
                        if fpath not in file_matches:
                            file_matches.add(fpath)
                            results.append(fpath)
                    elif output_mode == "count":
                        file_matches.setdefault(fpath, 0)
                        file_matches[fpath] = file_matches.get(fpath, 0) + 1
                    else:
                        results.append(f"{fpath}:{lineno}:{line.rstrip()}")

            if count > max_results:
                break
        if count > max_results:
            break

    if output_mode == "count":
        results = [f"{k}:{v}" for k, v in file_matches.items()]

    return "\n".join(results), count


async def grep_search(
    pattern: str,
    path: str | None = None,
    file_type: str | None = None,
    output_mode: str = "files_with_matches",
    context: int = 0,
    case_insensitive: bool = False,
    max_results: int = 250,
) -> ToolResponse:
    """Search file contents using regex patterns.

    Uses ripgrep (rg) when available, falls back to Python re module.

    Args:
        pattern: Regular expression pattern to search for.
        path: Directory or file to search. Defaults to cwd.
        file_type: File type filter (py, js, ts, go, rust, etc.).
        output_mode: 'files_with_matches' (default), 'content', or 'count'.
        context: Lines of context around matches (only for 'content' mode).
        case_insensitive: Case insensitive search. Default False.
        max_results: Maximum results. Default 250.

    Returns:
        ToolResponse with search results.
    """
    search_path = path or os.getcwd()

    if not os.path.exists(search_path):
        return ToolResponse(
            content=[TextBlock(text=f"Error: Path does not exist: {search_path}")],
        )

    # Try ripgrep first
    output, count = await _try_ripgrep(
        pattern, search_path, file_type, output_mode,
        context, case_insensitive, max_results,
    )

    # Fallback to Python if rg not available
    if output is None:
        output, count = await _python_fallback(
            pattern, search_path, file_type, output_mode,
            context, case_insensitive, max_results,
        )

    if not output:
        return ToolResponse(
            content=[TextBlock(text=f"No matches found for pattern '{pattern}' in {search_path}")],
            metadata={"count": 0},
        )

    return ToolResponse(
        content=[TextBlock(text=output)],
        metadata={"count": count},
    )
