# -*- coding: utf-8 -*-
"""Git utility functions for CodeAgent."""
import asyncio
import os
from pathlib import Path
from typing import NamedTuple


class GitInfo(NamedTuple):
    """Git repository information."""
    is_repo: bool
    root: str | None
    branch: str | None
    status: str | None
    remote_url: str | None


async def _run_git(cmd: str, cwd: str | None = None) -> tuple[str, int]:
    """Run a git command and return (stdout, returncode)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode("utf-8", errors="replace").strip(), proc.returncode


async def find_git_root(path: str | None = None) -> str | None:
    """Find the git repository root from the given path."""
    cwd = path or os.getcwd()
    output, rc = await _run_git("git rev-parse --show-toplevel", cwd=cwd)
    return output if rc == 0 else None


async def get_branch(cwd: str | None = None) -> str | None:
    """Get the current branch name."""
    output, rc = await _run_git("git branch --show-current", cwd=cwd)
    return output if rc == 0 else None


async def get_status_short(cwd: str | None = None) -> str | None:
    """Get short git status."""
    output, rc = await _run_git("git status --short", cwd=cwd)
    return output if rc == 0 else None


async def get_diff_stat(cwd: str | None = None) -> str | None:
    """Get diff stat."""
    output, rc = await _run_git("git diff --stat", cwd=cwd)
    return output if rc == 0 else None


async def is_git_repo(path: str | None = None) -> bool:
    """Check if the given path is inside a git repository."""
    return await find_git_root(path) is not None


async def get_git_info(path: str | None = None) -> GitInfo:
    """Gather all git info at once."""
    cwd = path or os.getcwd()
    root = await find_git_root(cwd)
    if root is None:
        return GitInfo(
            is_repo=False,
            root=None,
            branch=None,
            status=None,
            remote_url=None,
        )

    # Run remaining queries in parallel
    branch_coro = get_branch(root)
    status_coro = get_status_short(root)
    remote_coro = _run_git("git remote get-url origin", cwd=root)

    branch, status, (remote_url, remote_rc) = await asyncio.gather(
        branch_coro, status_coro, remote_coro,
    )

    return GitInfo(
        is_repo=True,
        root=root,
        branch=branch,
        status=status,
        remote_url=remote_url if remote_rc == 0 else None,
    )
