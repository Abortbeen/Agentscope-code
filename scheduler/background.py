# -*- coding: utf-8 -*-
"""Background task manager for long-running shell commands.

Implements R47 from the plan.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable

import shortuuid


@dataclass
class BackgroundTask:
    """A background shell task."""
    id: str
    command: str
    pid: int | None = None
    status: str = "running"  # running, completed, failed, cancelled
    output: str = ""
    exit_code: int | None = None
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None


class BackgroundTaskManager:
    """Manages background shell tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._asyncio_tasks: dict[str, asyncio.Task] = {}
        self._on_complete: Callable[[BackgroundTask], Awaitable[None]] | None = None

    def set_on_complete(
        self,
        callback: Callable[[BackgroundTask], Awaitable[None]],
    ) -> None:
        """Set callback for when a background task completes."""
        self._on_complete = callback

    async def run(self, command: str, cwd: str | None = None) -> str:
        """Start a background shell command.

        Args:
            command: Shell command to run.
            cwd: Working directory.

        Returns:
            Task ID.
        """
        task_id = shortuuid.uuid()[:8]
        bg_task = BackgroundTask(id=task_id, command=command)
        self._tasks[task_id] = bg_task

        async def _run():
            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
                bg_task.pid = proc.pid
                stdout, stderr = await proc.communicate()

                bg_task.output = stdout.decode("utf-8", errors="replace")
                if stderr:
                    bg_task.output += f"\nSTDERR:\n{stderr.decode('utf-8', errors='replace')}"
                bg_task.exit_code = proc.returncode
                bg_task.status = "completed" if proc.returncode == 0 else "failed"
            except Exception as e:
                bg_task.status = "failed"
                bg_task.output = str(e)
            finally:
                bg_task.finished_at = datetime.now()
                if self._on_complete:
                    await self._on_complete(bg_task)

        self._asyncio_tasks[task_id] = asyncio.create_task(_run())
        return task_id

    def get_task(self, task_id: str) -> BackgroundTask | None:
        """Get a background task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[BackgroundTask]:
        """List all background tasks."""
        return list(self._tasks.values())

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running background task."""
        atask = self._asyncio_tasks.get(task_id)
        if atask and not atask.done():
            atask.cancel()
            bg_task = self._tasks.get(task_id)
            if bg_task:
                bg_task.status = "cancelled"
                bg_task.finished_at = datetime.now()
            return True
        return False
