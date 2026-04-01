# -*- coding: utf-8 -*-
"""Git tools - status, diff, log, commit, and worktree management.

Implements R38-R40 from the plan.
"""
import asyncio
import os
import shlex
import shutil

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

CO_AUTHOR = "Co-Authored-By: CodeAgent <noreply@codeagent>"


async def _run_git(cmd: str, cwd: str | None = None) -> tuple[int, str, str]:
    """Run a git command and return (exit_code, stdout, stderr)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or os.getcwd(),
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )


async def git_status() -> ToolResponse:
    """Return current git status.

    Returns:
        ToolResponse with git status output.
    """
    exit_code, stdout, stderr = await _run_git("git status")
    if exit_code != 0:
        return ToolResponse(
            content=[TextBlock(text=f"Error running git status:\n{stderr}")],
        )
    return ToolResponse(
        content=[TextBlock(text=stdout or "(clean working tree)")],
    )


async def git_diff(
    path: str | None = None,
    staged: bool = False,
) -> ToolResponse:
    """Show git diff.

    Args:
        path: Optional file path to restrict the diff.
        staged: If True, show staged changes (--cached).

    Returns:
        ToolResponse with diff output.
    """
    cmd = "git diff"
    if staged:
        cmd += " --cached"
    if path:
        cmd += f" -- {shlex.quote(path)}"

    exit_code, stdout, stderr = await _run_git(cmd)
    if exit_code != 0:
        return ToolResponse(
            content=[TextBlock(text=f"Error running git diff:\n{stderr}")],
        )
    return ToolResponse(
        content=[TextBlock(text=stdout or "(no differences)")],
    )


async def git_log(count: int = 10) -> ToolResponse:
    """Show recent git commits.

    Args:
        count: Number of recent commits to show. Default 10.

    Returns:
        ToolResponse with log output.
    """
    cmd = f"git log --oneline --no-decorate -n {int(count)}"
    exit_code, stdout, stderr = await _run_git(cmd)
    if exit_code != 0:
        return ToolResponse(
            content=[TextBlock(text=f"Error running git log:\n{stderr}")],
        )
    return ToolResponse(
        content=[TextBlock(text=stdout or "(no commits)")],
    )


async def git_commit(
    message: str,
    files: list[str] | None = None,
) -> ToolResponse:
    """Create a git commit with Co-Authored-By attribution.

    Args:
        message: Commit message.
        files: Optional list of files to stage before committing.
            If None, commits whatever is already staged.

    Returns:
        ToolResponse with commit result.
    """
    if not message or not message.strip():
        return ToolResponse(
            content=[TextBlock(text="Error: Empty commit message.")],
        )

    # Stage files if specified
    if files:
        file_args = " ".join(shlex.quote(f) for f in files)
        exit_code, _, stderr = await _run_git(f"git add {file_args}")
        if exit_code != 0:
            return ToolResponse(
                content=[TextBlock(text=f"Error staging files:\n{stderr}")],
            )

    # Build commit message with co-author
    full_message = f"{message}\n\n{CO_AUTHOR}"
    cmd = f"git commit -m {shlex.quote(full_message)}"

    exit_code, stdout, stderr = await _run_git(cmd)
    if exit_code != 0:
        return ToolResponse(
            content=[TextBlock(text=f"Error creating commit:\n{stderr}")],
        )
    return ToolResponse(
        content=[TextBlock(text=stdout)],
    )


async def git_worktree_create(
    name: str,
    branch: str | None = None,
) -> ToolResponse:
    """Create a git worktree in .agent/worktrees/.

    Args:
        name: Name for the worktree directory.
        branch: Branch name to checkout. Creates a new branch if it doesn't exist.
            Defaults to the worktree name.

    Returns:
        ToolResponse with creation result.
    """
    worktree_base = os.path.join(os.getcwd(), ".agent", "worktrees")
    os.makedirs(worktree_base, exist_ok=True)

    worktree_path = os.path.join(worktree_base, name)
    if os.path.exists(worktree_path):
        return ToolResponse(
            content=[TextBlock(text=f"Error: Worktree already exists at {worktree_path}")],
        )

    branch_name = branch or name
    cmd = f"git worktree add {shlex.quote(worktree_path)} -b {shlex.quote(branch_name)}"

    exit_code, stdout, stderr = await _run_git(cmd)
    if exit_code != 0:
        # Branch may already exist, try without -b
        cmd = f"git worktree add {shlex.quote(worktree_path)} {shlex.quote(branch_name)}"
        exit_code, stdout, stderr = await _run_git(cmd)
        if exit_code != 0:
            return ToolResponse(
                content=[TextBlock(text=f"Error creating worktree:\n{stderr}")],
            )

    return ToolResponse(
        content=[TextBlock(
            text=f"Created worktree '{name}' at {worktree_path}\n{stdout}",
        )],
    )


async def git_worktree_remove(name: str) -> ToolResponse:
    """Remove a git worktree.

    Args:
        name: Name of the worktree to remove.

    Returns:
        ToolResponse with removal result.
    """
    worktree_path = os.path.join(os.getcwd(), ".agent", "worktrees", name)
    if not os.path.exists(worktree_path):
        return ToolResponse(
            content=[TextBlock(text=f"Error: Worktree not found at {worktree_path}")],
        )

    cmd = f"git worktree remove {shlex.quote(worktree_path)} --force"
    exit_code, stdout, stderr = await _run_git(cmd)
    if exit_code != 0:
        # Fallback: manual cleanup
        try:
            shutil.rmtree(worktree_path)
            await _run_git("git worktree prune")
            return ToolResponse(
                content=[TextBlock(
                    text=f"Removed worktree '{name}' (manual cleanup).",
                )],
            )
        except Exception as e:
            return ToolResponse(
                content=[TextBlock(text=f"Error removing worktree:\n{stderr}\n{e}")],
            )

    return ToolResponse(
        content=[TextBlock(text=f"Removed worktree '{name}'.\n{stdout}")],
    )
