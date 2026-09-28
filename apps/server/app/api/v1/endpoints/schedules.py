"""
Scheduled Task Endpoints.
Manage recurring background jobs (e.g. re-run a workflow on an interval).
"""

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.jobs.scheduler import get_schedule_service

router = APIRouter()


class CreateScheduleRequest(BaseModel):
    name: str = Field(default="", max_length=255)
    kind: str = Field(default="workflow.execute", description="workflow.execute | collection.execute")
    target_id: str = Field(..., min_length=1, description="Workflow or collection job id")
    interval_seconds: int = Field(..., ge=30, description="Run interval in seconds (min 30)")


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: str
    target_id: str
    interval_seconds: int
    enabled: bool
    last_run_at: Optional[Any] = None
    next_run_at: Optional[Any] = None
    created_at: Optional[Any] = None


@router.post("", response_model=ScheduleResponse, summary="Create a recurring schedule", status_code=status.HTTP_201_CREATED)
async def create_schedule(payload: CreateScheduleRequest) -> ScheduleResponse:
    """Schedules a workflow or collection job to run on an interval."""
    try:
        task = await get_schedule_service().create(
            name=payload.name, kind=payload.kind,
            target_id=payload.target_id, interval_seconds=payload.interval_seconds,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    return ScheduleResponse.model_validate(task, from_attributes=True)


@router.get("", response_model=List[ScheduleResponse], summary="List schedules", status_code=status.HTTP_200_OK)
async def list_schedules() -> List[ScheduleResponse]:
    tasks = await get_schedule_service().list()
    return [ScheduleResponse.model_validate(t, from_attributes=True) for t in tasks]


@router.delete("/{schedule_id}", summary="Delete a schedule", status_code=status.HTTP_200_OK)
async def delete_schedule(schedule_id: str) -> dict:
    if not await get_schedule_service().delete(schedule_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule '{schedule_id}' not found.")
    return {"id": schedule_id, "deleted": True}
