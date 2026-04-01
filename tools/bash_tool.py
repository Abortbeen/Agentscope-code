# -*- coding: utf-8 -*-
"""BashTool - Execute shell commands with timeout and streaming.

Implements R5 from the plan.
"""
import asyncio
import os
from typing import AsyncGenerator

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


async def bash_execute(
    command: str,
    timeout: int = 120000,
    working_dir: str | None = None,
    run_in_background: bool = False,
) -> ToolResponse | AsyncGenerator[ToolResponse, None]:
    """Execute a shell command and return its output.

    Args:
        command: The shell command to execute.
        timeout: Timeout in milliseconds (default 120000 = 2 minutes, max 600000).
        working_dir: Working directory for the command. Defaults to cwd.
        run_in_background: If True, run command in background and return immediately.

    Returns:
        ToolResponse with stdout, stderr, and exit code.
    """
    if not command or not command.strip():
        return ToolResponse(
            content=[TextBlock(text="Error: Empty command provided.")],
        )

    # Validate timeout
    timeout_sec = min(timeout, 600000) / 1000.0
    cwd = working_dir or os.getcwd()

    if not os.path.isdir(cwd):
        return ToolResponse(
            content=[TextBlock(text=f"Error: Working directory does not exist: {cwd}")],
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        if run_in_background:
            return ToolResponse(
                content=[TextBlock(
                    text=f"Command started in background (PID: {proc.pid}).\n"
                    f"Command: {command}",
                )],
                metadata={"pid": proc.pid, "background": True},
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResponse(
                content=[TextBlock(
                    text=f"Error: Command timed out after {timeout_sec:.0f}s and was killed.\n"
                    f"Command: {command}",
                )],
                metadata={"exit_code": -1, "timed_out": True},
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode

        # Build output
        parts = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(f"STDERR:\n{stderr}")

        output = "\n".join(parts) if parts else "(no output)"

        # Truncate very long output
        max_len = 100000
        if len(output) > max_len:
            output = (
                output[:max_len // 2]
                + f"\n\n... (truncated {len(output) - max_len} chars) ...\n\n"
                + output[-max_len // 2:]
            )

        return ToolResponse(
            content=[TextBlock(text=output)],
            metadata={"exit_code": exit_code},
        )

    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error executing command: {e}")],
            metadata={"exit_code": -1},
        )
