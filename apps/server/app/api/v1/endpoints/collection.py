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
from app.collection.service import CollectionService
from app.db.session import get_db
from app.core.logger import logger

router = APIRouter()
collection_service = CollectionService()


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
    "/jobs/{job_id}",
    summary="Get collection job status and audit statistics",
    status_code=status.HTTP_200_OK,
)
async def get_collection_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns collection job lifecycle state, duration, document counts, and error reports.
    """
    job = await collection_service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CollectionJob '{job_id}' not found.",
        )

    return {
        "job_id": job.id,
        "request_id": job.request_id,
        "workflow_id": job.workflow_id,
        "status": job.status,
        "collection_request": job.collection_request,
        "discovered_sources": job.discovered_sources,
        "selected_sources": job.selected_sources,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "metadata": job.metadata_,
        "error": job.error,
        "errors": job.errors,
    }


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
    return JobDocumentsResponse(
        job_id=job_id,
        total=len(docs),
        documents=docs,
    )
