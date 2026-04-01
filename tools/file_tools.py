# -*- coding: utf-8 -*-
"""File tools - Read, Write, Edit operations.

Implements R6 from the plan.
"""
import os
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


async def file_read(
    file_path: str,
    offset: int = 0,
    limit: int = 2000,
) -> ToolResponse:
    """Read a file and return its contents with line numbers.

    Args:
        file_path: Absolute path to the file to read.
        offset: Line number to start reading from (0-based). Default 0.
        limit: Maximum number of lines to read. Default 2000.

    Returns:
        ToolResponse with file content in 'cat -n' format.
    """
    path = Path(file_path)

    if not path.exists():
        return ToolResponse(
            content=[TextBlock(text=f"Error: File does not exist: {file_path}")],
        )

    if path.is_dir():
        return ToolResponse(
            content=[TextBlock(
                text=f"Error: Path is a directory, not a file: {file_path}. "
                "Use bash 'ls' to list directory contents.",
            )],
        )

    # Check for binary files
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return ToolResponse(
                    content=[TextBlock(
                        text=f"Error: File appears to be binary: {file_path}",
                    )],
                )
    except OSError as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error reading file: {e}")],
        )

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total = len(all_lines)
        start = max(0, offset)
        end = min(total, start + limit)
        selected = all_lines[start:end]

        # Format with line numbers (1-based)
        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            numbered.append(f"{i}\t{line.rstrip()}")

        output = "\n".join(numbered)

        if end < total:
            output += f"\n\n... ({total - end} more lines, use offset={end} to continue)"

        return ToolResponse(
            content=[TextBlock(text=output if output else "(empty file)")],
            metadata={"total_lines": total, "offset": start, "limit": limit},
        )

    except OSError as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error reading file: {e}")],
        )


async def file_write(
    file_path: str,
    content: str,
) -> ToolResponse:
    """Write content to a file, creating parent directories as needed.

    This overwrites the entire file. Use file_edit for partial modifications.

    Args:
        file_path: Absolute path to the file to write.
        content: The content to write.

    Returns:
        ToolResponse confirming the write.
    """
    path = Path(file_path)

    try:
        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return ToolResponse(
            content=[TextBlock(
                text=f"Successfully wrote {line_count} lines to {file_path}",
            )],
            metadata={"lines_written": line_count},
        )

    except OSError as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error writing file: {e}")],
        )


async def file_edit(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> ToolResponse:
    """Perform exact string replacement in a file.

    Args:
        file_path: Absolute path to the file to edit.
        old_string: The exact text to find and replace (must be unique unless replace_all=True).
        new_string: The replacement text (must differ from old_string).
        replace_all: If True, replace all occurrences. Default False.

    Returns:
        ToolResponse confirming the edit.
    """
    if old_string == new_string:
        return ToolResponse(
            content=[TextBlock(text="Error: old_string and new_string are identical.")],
        )

    path = Path(file_path)

    if not path.exists():
        return ToolResponse(
            content=[TextBlock(text=f"Error: File does not exist: {file_path}")],
        )

    try:
        original = path.read_text(encoding="utf-8")
    except OSError as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error reading file: {e}")],
        )

    count = original.count(old_string)

    if count == 0:
        return ToolResponse(
            content=[TextBlock(
                text=f"Error: old_string not found in {file_path}. "
                "Make sure the string matches exactly, including whitespace and indentation.",
            )],
        )

    if count > 1 and not replace_all:
        return ToolResponse(
            content=[TextBlock(
                text=f"Error: old_string found {count} times in {file_path}. "
                "Provide more surrounding context to make it unique, "
                "or set replace_all=True to replace all occurrences.",
            )],
        )

    if replace_all:
        new_content = original.replace(old_string, new_string)
    else:
        new_content = original.replace(old_string, new_string, 1)

    try:
        path.write_text(new_content, encoding="utf-8")
        return ToolResponse(
            content=[TextBlock(
                text=f"Successfully edited {file_path} ({count} replacement{'s' if count > 1 else ''}).",
            )],
            metadata={"replacements": count},
        )
    except OSError as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error writing file: {e}")],
        )
