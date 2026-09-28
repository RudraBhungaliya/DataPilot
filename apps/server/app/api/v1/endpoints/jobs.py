"""
Background Job Endpoints.
Inspect queued/running/completed background tasks.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.jobs.queue import queue_depth
from app.jobs.service import get_job_service

router = APIRouter()


class JobSubmitResponse(BaseModel):
    id: str
    kind: str
    status: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: str
    payload: dict = Field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[Any] = None
    started_at: Optional[Any] = None
    finished_at: Optional[Any] = None


class QueueStats(BaseModel):
    depth: int


@router.get("", response_model=List[JobResponse], summary="List background jobs", status_code=status.HTTP_200_OK)
async def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> List[JobResponse]:
    """Returns recent background jobs, most recent first."""
    jobs = await get_job_service().list_jobs(limit=limit)
    return [JobResponse.model_validate(j, from_attributes=True) for j in jobs]


@router.get("/stats", response_model=QueueStats, summary="Background queue depth", status_code=status.HTTP_200_OK)
async def get_queue_stats() -> QueueStats:
    """Returns the current number of queued jobs."""
    return QueueStats(depth=await queue_depth())


@router.get("/{job_id}", response_model=JobResponse, summary="Get a background job", status_code=status.HTTP_200_OK)
async def get_job(job_id: str) -> JobResponse:
    """Returns a single background job's status and result."""
    job = await get_job_service().get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")
    return JobResponse.model_validate(job, from_attributes=True)
