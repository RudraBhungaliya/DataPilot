"""
Collection Engine Endpoints.
Provides REST APIs for job creation, source discovery, collection execution, and document inspection.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.collection.schemas import (
    CollectionRequest,
    CollectionResult,
    SourceDefinition,
    RawDocument,
)
from app.collection.dependencies import get_collection_service
from app.api.v1.endpoints.jobs import JobSubmitResponse
from app.jobs.service import get_job_service
from app.db.session import get_db
from app.core.logger import logger

router = APIRouter()
collection_service = get_collection_service()


class CreateJobRequest(BaseModel):
    collection_request: CollectionRequest


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


class DiscoverSourcesResponse(BaseModel):
    job_id: str
    sources_discovered: int = 0
    sources: List[SourceDefinition]


class JobDocumentsResponse(BaseModel):
    job_id: str
    total: int
    documents: List[RawDocument]


def _serialize_job(job) -> Dict[str, Any]:
    """Serializes a CollectionJob (ORM or in-memory) into an API dictionary."""
    return {
        "id": job.id,
        "job_id": job.id,
        "request_id": job.request_id,
        "workflow_id": job.workflow_id,
        "status": job.status,
        "source": job.source,
        "progress": job.progress,
        "current_step": job.current_step,
        "human_action_required": job.human_action_required,
        "human_action_reason": job.human_action_reason,
        "checkpoint": job.checkpoint,
        "collection_request": job.collection_request,
        "discovered_sources": job.discovered_sources,
        "selected_sources": job.selected_sources,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if getattr(job, "created_at", None) else None,
        "updated_at": job.updated_at.isoformat() if getattr(job, "updated_at", None) else None,
        "metadata": job.metadata_,
        "error": job.error,
        "errors": job.errors,
    }


@router.post(
    "/jobs",
    response_model=CreateJobResponse,
    summary="Create a new collection job",
    status_code=status.HTTP_201_CREATED,
)
async def create_collection_job(
    payload: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateJobResponse:
    """
    Initializes a new data collection job based on an objective specification.
    """
    try:
        job = await collection_service.create_job(request=payload.collection_request, db=db)
        return CreateJobResponse(job_id=job.id, status=job.status)
    except Exception as e:
        logger.error(f"Failed to create collection job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to create collection job: {str(e)}",
        )


@router.post(
    "/jobs/{job_id}/discover",
    response_model=DiscoverSourcesResponse,
    summary="Discover eligible sources for a collection job",
    status_code=status.HTTP_200_OK,
)
async def discover_sources_for_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> DiscoverSourcesResponse:
    """
    Evaluates registry and providers to find eligible sources matching the job's collection request.
    """
    job = await collection_service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CollectionJob '{job_id}' not found.",
        )

    try:
        request = CollectionRequest.model_validate(job.collection_request)
        sources = await collection_service.discover_sources(request)
        return DiscoverSourcesResponse(job_id=job_id, sources_discovered=len(sources), sources=sources)
    except Exception as e:
        logger.error(f"Error discovering sources for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Source discovery failed: {str(e)}",
        )


@router.post(
    "/jobs/{job_id}/execute",
    response_model=CollectionResult,
    summary="Execute collection job across discovered sources",
    status_code=status.HTTP_200_OK,
)
async def execute_collection_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> CollectionResult:
    """
    Executes raw data gathering across selected sources with rate limits, retries, and CAPTCHA fallbacks.
    """
    try:
        result = await collection_service.execute_job(job_id=job_id, db=db)
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Collection job execution failed for {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job execution failed: {str(e)}",
        )


@router.get(
    "/jobs",
    response_model=List[Dict[str, Any]],
    summary="List recent collection jobs",
    status_code=status.HTTP_200_OK,
)
async def list_collection_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns the most recent collection jobs with their lifecycle state."""
    jobs = await collection_service.list_recent_jobs(limit=limit, db=db)
    return [_serialize_job(job) for job in jobs]


@router.get(
    "/documents",
    response_model=List[RawDocument],
    summary="List recent raw documents across all jobs",
    status_code=status.HTTP_200_OK,
)
async def list_recent_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[RawDocument]:
    """Returns the most recently collected raw documents with bounded content previews."""
    docs = await collection_service.get_recent_documents(limit=limit, offset=offset, db=db)
    preview_limit = 2000
    for doc in docs:
        if doc.content and len(doc.content) > preview_limit:
            doc.content = doc.content[:preview_limit]
    return docs


@router.post(
    "/jobs/{job_id}/execute-async",
    response_model=JobSubmitResponse,
    summary="Execute a collection job in the background",
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_collection_job_async(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobSubmitResponse:
    """
    Queues a collection job on the background worker and returns a job handle.
    Poll GET /api/v1/jobs/{job_id} for status and results.
    """
    job = await collection_service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CollectionJob '{job_id}' not found.",
        )
    task = await get_job_service().submit("collection.execute", {"collection_job_id": job_id})
    return JobSubmitResponse(id=task.id, kind=task.kind, status=task.status)


@router.get(
    "/jobs/{job_id}",
    summary="Get collection job status and audit statistics",
    status_code=status.HTTP_200_OK,
)
async def get_collection_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns collection job lifecycle state, duration, document counts, and human action status.
    """
    job = await collection_service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CollectionJob '{job_id}' not found.",
        )

    return _serialize_job(job)


@router.post(
    "/jobs/{job_id}/resume",
    response_model=CollectionResult,
    summary="Resume a collection job paused for human intervention",
    status_code=status.HTTP_200_OK,
)
async def resume_collection_job(
    job_id: str,
    skip_source: bool = Query(default=False, description="Abandon the blocked source and use alternatives"),
    db: AsyncSession = Depends(get_db),
) -> CollectionResult:
    """
    Resumes a collection job that is in HUMAN_ACTION_REQUIRED status from its safe checkpoint.
    """
    job = await collection_service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CollectionJob '{job_id}' not found.",
        )

    if job.status != "HUMAN_ACTION_REQUIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot resume job '{job_id}' with status '{job.status}'. "
                "Only jobs in 'HUMAN_ACTION_REQUIRED' status can be resumed."
            ),
        )

    try:
        result = await collection_service.resume_job(job_id=job_id, db=db, skip_current_source=skip_source)
        return result
    except Exception as e:
        logger.error(f"Failed to resume collection job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume collection job: {str(e)}",
        )



@router.get(
    "/jobs/{job_id}/documents",
    response_model=JobDocumentsResponse,
    summary="Get raw collected documents for a job",
    status_code=status.HTTP_200_OK,
)
async def get_job_documents(
    job_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> JobDocumentsResponse:
    """
    Returns raw collected documents (HTML, JSON, XML) gathered during the job.
    """
    job = await collection_service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CollectionJob '{job_id}' not found.",
        )

    docs = await collection_service.get_documents(job_id=job_id, limit=limit, offset=offset, db=db)
    # Avoid returning multi-MB raw payloads in list responses; expose a bounded preview.
    preview_limit = 2000
    for doc in docs:
        if doc.content and len(doc.content) > preview_limit:
            doc.content = doc.content[:preview_limit]
    return JobDocumentsResponse(
        job_id=job_id,
        total=len(docs),
        documents=docs,
    )
