"""
Background job service.

Tracks job lifecycle in memory (authoritative for the process) with best-effort
database persistence for durability.
"""

import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import select, desc

from app.core.logger import logger
from app.db.session import AsyncSessionLocal
from app.jobs import queue
from app.models.background_job import BackgroundJob


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobService:
    """Submits and tracks background jobs."""

    def __init__(self) -> None:
        self._memory: Dict[str, BackgroundJob] = {}

    async def submit(self, kind: str, payload: Optional[Dict[str, Any]] = None) -> BackgroundJob:
        """Creates a job, persists it best-effort, and enqueues it."""
        job = BackgroundJob(
            id=f"task_{secrets.token_hex(6)}",
            kind=kind,
            status=JobStatus.QUEUED.value,
            payload=payload or {},
            progress=0.0,
            cancel_requested=False,
        )
        self._memory[job.id] = job
        await self._persist(job)
        await queue.enqueue(job.id)
        logger.info(f"Queued {kind} job '{job.id}'")
        return job

    async def _persist(self, job: BackgroundJob) -> None:
        try:
            async with AsyncSessionLocal() as db:
                db.add(job)
                await db.commit()
        except Exception as e:
            logger.debug(f"Background job '{job.id}' not persisted: {e}")

    async def _update(self, job_id: str, **fields: Any) -> Optional[BackgroundJob]:
        job = self._memory.get(job_id)
        if job is not None:
            for key, value in fields.items():
                setattr(job, key, value)
        try:
            async with AsyncSessionLocal() as db:
                row = await db.get(BackgroundJob, job_id)
                if row is not None:
                    for key, value in fields.items():
                        setattr(row, key, value)
                    await db.commit()
                    if job is None:
                        job = row
                        self._memory[job_id] = row
        except Exception as e:
            logger.debug(f"Background job '{job_id}' update not persisted: {e}")
        return job

    async def mark_running(self, job_id: str) -> None:
        await self._update(
            job_id,
            status=JobStatus.RUNNING.value,
            progress=0.1,
            started_at=datetime.now(timezone.utc),
        )

    async def mark_completed(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        await self._update(
            job_id,
            status=JobStatus.COMPLETED.value,
            result=result or {},
            progress=1.0,
            finished_at=datetime.now(timezone.utc),
        )

    async def mark_failed(self, job_id: str, error: str) -> None:
        await self._update(
            job_id,
            status=JobStatus.FAILED.value,
            error=error[:2000],
            finished_at=datetime.now(timezone.utc),
        )

    async def mark_cancelled(self, job_id: str) -> None:
        await self._update(
            job_id,
            status=JobStatus.CANCELLED.value,
            finished_at=datetime.now(timezone.utc),
        )

    async def cancel(self, job_id: str) -> bool:
        """Requests cancellation of a queued/running job. Returns True if applied."""
        job = await self.get(job_id)
        if job is None:
            return False
        if job.status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
            return False
        await self._update(job_id, cancel_requested=True, status=JobStatus.CANCELLED.value)
        logger.info(f"Background job '{job_id}' cancelled.")
        return True

    async def retry(self, job_id: str) -> Optional[BackgroundJob]:
        """Re-queues a finished job with the same kind and payload."""
        job = await self.get(job_id)
        if job is None:
            return None
        return await self.submit(job.kind, dict(job.payload or {}))

    async def set_progress(self, job_id: str, progress: float) -> None:
        await self._update(job_id, progress=max(0.0, min(1.0, float(progress))))

    async def get(self, job_id: str) -> Optional[BackgroundJob]:
        job = self._memory.get(job_id)
        if job is not None:
            return job
        try:
            async with AsyncSessionLocal() as db:
                row = await db.get(BackgroundJob, job_id)
                if row is not None:
                    self._memory[job_id] = row
                    return row
        except Exception as e:
            logger.debug(f"Background job '{job_id}' not found in DB: {e}")
        return None

    async def list_jobs(self, limit: int = 50) -> List[BackgroundJob]:
        if self._memory:
            return list(self._memory.values())[::-1][:limit]
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(BackgroundJob).order_by(desc(BackgroundJob.created_at)).limit(limit)
                )
                return list(res.scalars().all())
        except Exception as e:
            logger.debug(f"Background jobs not listed from DB: {e}")
            return []


_job_service: Optional[JobService] = None


def get_job_service() -> JobService:
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service
