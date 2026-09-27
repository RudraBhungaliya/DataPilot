"""
Collection Service.
Orchestrates the entire Source Collection lifecycle:
Job creation, Source Discovery, Source Selection, Routing, Collection Execution,
and Document Retrieval.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.collection.schemas import (
    CollectionRequest,
    CollectionResult,
    SourceDefinition,
    RawDocument,
    JobStatus,
    SourceStatus,
)
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.discovery.registry import SourceRegistry
from app.collection.manager import CollectionManager
from app.collection.storage.document_store import RawDocumentStore
from app.models.collection_job import CollectionJob
from app.core.logger import logger


class CollectionService:
    """
    Business service layer managing collection jobs and document acquisition.
    """

    def __init__(
        self,
        registry: Optional[SourceRegistry] = None,
        discovery: Optional[SourceDiscovery] = None,
        manager: Optional[CollectionManager] = None,
        document_store: Optional[RawDocumentStore] = None,
    ):
        self.registry = registry or SourceRegistry()
        self.discovery = discovery or SourceDiscovery(registry=self.registry)
        self.document_store = document_store or RawDocumentStore()
        self.manager = manager or CollectionManager(
            discovery=self.discovery,
            document_store=self.document_store,
        )
        self._memory_jobs: Dict[str, CollectionJob] = {}

    async def create_job(
        self,
        request: CollectionRequest,
        db: Optional[AsyncSession] = None,
    ) -> CollectionJob:
        """
        Creates and persists a new CollectionJob record.
        """
        job_id = f"job_{request.request_id.replace('colreq_', '')}"
        job = CollectionJob(
            id=job_id,
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            status=JobStatus.CREATED.value,
            collection_request=request.model_dump(mode="json"),
            discovered_sources=[],
            selected_sources=[],
            metadata_={
                "created_at": datetime.now(timezone.utc).isoformat(),
                "entity": request.entity,
            },
            errors=[],
        )

        self._memory_jobs[job_id] = job

        if db is not None:
            try:
                db.add(job)
                await db.commit()
                await db.refresh(job)
                logger.info(f"CollectionJob '{job_id}' created in database.")
            except Exception as e:
                logger.warning(f"Could not persist CollectionJob '{job_id}' to DB (cached in memory): {e}")
                await db.rollback()

        return job

    async def discover_sources(self, request: CollectionRequest) -> List[SourceDefinition]:
        """
        Discovers eligible sources for a CollectionRequest.
        """
        return await self.discovery.discover_sources(request)

    def select_sources(
        self,
        discovered: List[SourceDefinition],
        request: CollectionRequest,
    ) -> List[SourceDefinition]:
        """
        Filters and selects sources using deterministic rules:
        - Active status only
        - Max sources limit
        - Exclude disabled/blocked sources
        """
        eligible = [s for s in discovered if s.status == SourceStatus.ACTIVE]
        max_sources = request.limits.max_sources if request.limits else 10
        return eligible[:max_sources]

    async def execute_job(
        self,
        job_id: str,
        db: Optional[AsyncSession] = None,
    ) -> CollectionResult:
        """
        Executes a collection job: discovers sources, selects sources, runs collection manager,
        and records the outcome.
        """
        job = await self.get_job(job_id=job_id, db=db)
        if not job:
            raise ValueError(f"CollectionJob with ID '{job_id}' not found.")

        req_data = job.collection_request
        request = CollectionRequest.model_validate(req_data)

        # 1. Discovery stage
        job.status = JobStatus.DISCOVERING.value
        discovered = await self.discover_sources(request)
        job.discovered_sources = [s.model_dump(mode="json") for s in discovered]

        # 2. Selection stage
        selected = self.select_sources(discovered, request)
        job.selected_sources = [s.model_dump(mode="json") for s in selected]

        if db is not None:
            try:
                await db.commit()
            except Exception:
                await db.rollback()

        # 3. Execution stage
        job.status = JobStatus.COLLECTING.value
        job.started_at = datetime.now(timezone.utc)
        if db is not None:
            try:
                await db.commit()
            except Exception:
                await db.rollback()

        # Run collection manager
        result = await self.manager.execute_job(
            request=request,
            sources=selected,
            db=db,
        )

        # 4. Finalize state
        job.status = result.status
        job.completed_at = datetime.now(timezone.utc)
        job.errors = result.errors
        job.metadata_.update(result.metadata.model_dump())
        if result.errors:
            job.error = str(result.errors[0].get("error", "One or more collection errors occurred"))

        if db is not None:
            try:
                await db.commit()
                await db.refresh(job)
            except Exception as e:
                logger.warning(f"Could not update finished job state in DB: {e}")
                await db.rollback()

        return result

    async def get_job(
        self,
        job_id: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[CollectionJob]:
        """Fetches a CollectionJob by ID."""
        if db is not None:
            try:
                stmt = select(CollectionJob).where(CollectionJob.id == job_id)
                res = await db.execute(stmt)
                db_job = res.scalar_one_or_none()
                if db_job:
                    return db_job
            except Exception as e:
                logger.warning(f"Failed to query CollectionJob {job_id} from DB: {e}")

        return self._memory_jobs.get(job_id)

    async def get_documents(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
        db: Optional[AsyncSession] = None,
    ) -> List[RawDocument]:
        """Retrieves raw documents gathered for a specific job."""
        return await self.document_store.list_by_job(job_id=job_id, limit=limit, offset=offset, db=db)
