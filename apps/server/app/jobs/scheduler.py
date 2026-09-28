"""
Recurring job scheduler.

Stores schedules in memory (authoritative for the process) with best-effort
database persistence, and enqueues due runs via the job service.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select

from app.core.logger import logger
from app.db.session import AsyncSessionLocal
from app.jobs.service import get_job_service
from app.models.scheduled_task import ScheduledTask

ALLOWED_KINDS = {"workflow.execute", "collection.execute"}


class ScheduleService:
    """Creates and runs recurring background jobs."""

    def __init__(self) -> None:
        self._memory: Dict[str, ScheduledTask] = {}

    async def create(
        self,
        name: str,
        kind: str,
        target_id: str,
        interval_seconds: int,
    ) -> ScheduledTask:
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"Unsupported schedule kind '{kind}'. Allowed: {sorted(ALLOWED_KINDS)}")
        if interval_seconds < 30:
            raise ValueError("interval_seconds must be at least 30")

        now = datetime.now(timezone.utc)
        task = ScheduledTask(
            id=f"sch_{secrets.token_hex(6)}",
            name=name or f"{kind}:{target_id}",
            kind=kind,
            target_id=target_id,
            interval_seconds=interval_seconds,
            enabled=True,
            next_run_at=now + timedelta(seconds=interval_seconds),
        )
        self._memory[task.id] = task
        try:
            async with AsyncSessionLocal() as db:
                db.add(task)
                await db.commit()
        except Exception as e:
            logger.debug(f"Schedule '{task.id}' not persisted: {e}")
        logger.info(f"Created schedule {task.id} ({kind} every {interval_seconds}s)")
        return task

    async def list(self) -> List[ScheduledTask]:
        if self._memory:
            return list(self._memory.values())
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(select(ScheduledTask).order_by(ScheduledTask.created_at.desc()))
                return list(res.scalars().all())
        except Exception as e:
            logger.debug(f"Schedules not listed from DB: {e}")
            return []

    async def get(self, schedule_id: str) -> Optional[ScheduledTask]:
        if schedule_id in self._memory:
            return self._memory[schedule_id]
        try:
            async with AsyncSessionLocal() as db:
                row = await db.get(ScheduledTask, schedule_id)
                if row is not None:
                    self._memory[schedule_id] = row
                    return row
        except Exception:
            pass
        return None

    async def delete(self, schedule_id: str) -> bool:
        existed = schedule_id in self._memory
        self._memory.pop(schedule_id, None)
        try:
            async with AsyncSessionLocal() as db:
                row = await db.get(ScheduledTask, schedule_id)
                if row is not None:
                    await db.delete(row)
                    await db.commit()
                    existed = True
        except Exception as e:
            logger.debug(f"Schedule '{schedule_id}' not deleted from DB: {e}")
        return existed

    async def run_due(self) -> int:
        """Enqueues jobs for schedules whose next_run_at has passed. Returns count."""
        now = datetime.now(timezone.utc)
        enqueued = 0
        for task in list(self._memory.values()):
            if not task.enabled:
                continue
            next_run = task.next_run_at
            if next_run is not None and next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            if next_run is not None and next_run > now:
                continue

            payload = (
                {"workflow_id": task.target_id}
                if task.kind == "workflow.execute"
                else {"collection_job_id": task.target_id}
            )
            try:
                await get_job_service().submit(task.kind, payload)
                task.last_run_at = now
                task.next_run_at = now + timedelta(seconds=task.interval_seconds)
                enqueued += 1
            except Exception as e:
                logger.warning(f"Schedule {task.id} could not enqueue: {e}")
        return enqueued


_schedule_service: Optional[ScheduleService] = None


def get_schedule_service() -> ScheduleService:
    global _schedule_service
    if _schedule_service is None:
        _schedule_service = ScheduleService()
    return _schedule_service
