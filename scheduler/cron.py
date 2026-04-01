# -*- coding: utf-8 -*-
"""Cron scheduler - schedule recurring tasks within a session.

Implements R46 from the plan.
Uses croniter for cron expression parsing and asyncio for scheduling.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable

import shortuuid


@dataclass
class CronJob:
    """A scheduled cron job."""
    id: str
    expression: str
    prompt: str
    recurring: bool = True
    active: bool = True
    last_run: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)


class CronScheduler:
    """Manages cron-based scheduled tasks."""

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._task: asyncio.Task | None = None
        self._callback: Callable[[str], Awaitable[None]] | None = None

    def set_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Set the callback to invoke when a cron job triggers."""
        self._callback = callback

    def create_job(
        self,
        expression: str,
        prompt: str,
        recurring: bool = True,
    ) -> str:
        """Create a new cron job.

        Args:
            expression: Cron expression (e.g., '*/5 * * * *').
            prompt: The prompt to inject when triggered.
            recurring: If True, repeats; if False, runs once.

        Returns:
            The job ID.
        """
        try:
            from croniter import croniter
            # Validate expression
            croniter(expression)
        except (ImportError, ValueError) as e:
            raise ValueError(f"Invalid cron expression '{expression}': {e}")

        job_id = shortuuid.uuid()[:8]
        self._jobs[job_id] = CronJob(
            id=job_id,
            expression=expression,
            prompt=prompt,
            recurring=recurring,
        )
        return job_id

    def delete_job(self, job_id: str) -> bool:
        """Delete a cron job."""
        return self._jobs.pop(job_id, None) is not None

    def list_jobs(self) -> list[CronJob]:
        """List all active cron jobs."""
        return [j for j in self._jobs.values() if j.active]

    async def start(self) -> None:
        """Start the cron scheduler loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the cron scheduler."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        """Main scheduler loop, checks every 30 seconds."""
        from croniter import croniter

        while True:
            now = datetime.now()
            for job in list(self._jobs.values()):
                if not job.active:
                    continue

                cron = croniter(job.expression, job.last_run or job.created_at)
                next_run = cron.get_next(datetime)

                if next_run <= now:
                    job.last_run = now
                    if self._callback:
                        try:
                            await self._callback(job.prompt)
                        except Exception:
                            pass

                    if not job.recurring:
                        job.active = False

            await asyncio.sleep(30)
