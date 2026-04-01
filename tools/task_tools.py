# -*- coding: utf-8 -*-
"""TaskBoard tools - create, update, list tasks for multi-agent coordination.

Implements R13 from the plan.
Uses in-memory dict with JSON file persistence.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

import shortuuid

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


@dataclass
class Task:
    """A task in the task board."""
    id: str
    subject: str
    description: str = ""
    status: str = "pending"  # pending, in_progress, completed, blocked
    assignee: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TaskBoard:
    """In-memory task board with JSON persistence."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._tasks: dict[str, Task] = {}
        self._persist_path = persist_path

    def create(self, subject: str, description: str = "", assignee: str | None = None) -> Task:
        task_id = shortuuid.uuid()[:8]
        task = Task(
            id=task_id,
            subject=subject,
            description=description,
            assignee=assignee,
        )
        self._tasks[task_id] = task
        self._persist()
        return task

    def update(
        self,
        task_id: str,
        status: str | None = None,
        assignee: str | None = None,
        description: str | None = None,
    ) -> Task | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        if status:
            task.status = status
        if assignee is not None:
            task.assignee = assignee
        if description is not None:
            task.description = description
        task.updated_at = datetime.now().isoformat()
        self._persist()
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_all(self) -> list[Task]:
        return list(self._tasks.values())

    def _persist(self) -> None:
        if not self._persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w") as f:
                json.dump(
                    {tid: asdict(t) for tid, t in self._tasks.items()},
                    f, indent=2,
                )
        except OSError:
            pass


# Global task board instance
_board = TaskBoard()


async def task_create(
    subject: str,
    description: str = "",
    assignee: str | None = None,
) -> ToolResponse:
    """Create a new task.

    Args:
        subject: Short task title.
        description: Detailed description.
        assignee: Agent name to assign to.

    Returns:
        ToolResponse with the created task.
    """
    task = _board.create(subject, description, assignee)
    return ToolResponse(
        content=[TextBlock(text=f"Task created: [{task.id}] {task.subject}")],
        metadata={"task_id": task.id},
    )


async def task_update(
    task_id: str,
    status: str | None = None,
    assignee: str | None = None,
    description: str | None = None,
) -> ToolResponse:
    """Update a task.

    Args:
        task_id: The task ID.
        status: New status (pending/in_progress/completed/blocked).
        assignee: New assignee.
        description: Updated description.

    Returns:
        ToolResponse confirming the update.
    """
    task = _board.update(task_id, status, assignee, description)
    if task is None:
        return ToolResponse(
            content=[TextBlock(text=f"Error: Task '{task_id}' not found.")],
        )
    return ToolResponse(
        content=[TextBlock(text=f"Task updated: [{task.id}] {task.status} - {task.subject}")],
    )


async def task_list() -> ToolResponse:
    """List all tasks.

    Returns:
        ToolResponse with task summary.
    """
    tasks = _board.list_all()
    if not tasks:
        return ToolResponse(
            content=[TextBlock(text="No tasks.")],
        )

    lines = []
    for t in tasks:
        assignee = f" @{t.assignee}" if t.assignee else ""
        lines.append(f"[{t.id}] {t.status:12s} {t.subject}{assignee}")

    return ToolResponse(
        content=[TextBlock(text="\n".join(lines))],
        metadata={"count": len(tasks)},
    )
