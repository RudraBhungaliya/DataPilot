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
from app.core.config import settings
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

    def _remember_job(self, job: CollectionJob) -> None:
        """Stores a job in the in-memory fallback map, evicting oldest beyond the bound."""
        self._memory_jobs[job.id] = job
        overflow = len(self._memory_jobs) - settings.DATAPILOT_MAX_IN_MEMORY_JOBS
        if overflow > 0:
            for key in list(self._memory_jobs.keys())[:overflow]:
                self._memory_jobs.pop(key, None)

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
            status=JobStatus.PENDING.value,
            current_step="PENDING",
            progress=0.0,
            human_action_required=False,
            human_action_reason=None,
            checkpoint=None,
            collection_request=request.model_dump(mode="json"),
            discovered_sources=[],
            selected_sources=[],
            metadata_={
                "created_at": datetime.now(timezone.utc).isoformat(),
                "entity": request.entity,
            },
            errors=[],
        )

        self._remember_job(job)

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
        and records the outcome. Supports entering HUMAN_ACTION_REQUIRED when blocked by CAPTCHA.
        """
        job = await self.get_job(job_id=job_id, db=db)
        if not job:
            raise ValueError(f"CollectionJob with ID '{job_id}' not found.")

        req_data = job.collection_request
        request = CollectionRequest.model_validate(req_data)

        # 1. Discovery stage
        job.status = JobStatus.RUNNING.value
        job.current_step = "SOURCE_DISCOVERY"
        job.progress = 0.2
        discovered = await self.discover_sources(request)
        job.discovered_sources = [s.model_dump(mode="json") for s in discovered]

        # 2. Selection stage
        selected = self.select_sources(discovered, request)
        job.selected_sources = [s.model_dump(mode="json") for s in selected]
        if selected:
            job.source = selected[0].model_dump(mode="json")

        if db is not None:
            try:
                await db.commit()
            except Exception:
                await db.rollback()

        # 3. Execution stage
        job.status = JobStatus.RUNNING.value
        job.current_step = "SOURCE_COLLECTION"
        job.progress = 0.5
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
            job_id=job.id,
        )

        # 4. Finalize state
        job.status = result.status
        job.errors = result.errors
        job.metadata_.update(result.metadata.model_dump())

        if result.status == JobStatus.HUMAN_ACTION_REQUIRED.value:
            job.human_action_required = True
            job.human_action_reason = result.human_action_reason or "CAPTCHA_REQUIRED"
            job.checkpoint = result.checkpoint
            job.current_step = "HUMAN_ACTION_REQUIRED"
            logger.info(f"CollectionJob '{job_id}' paused: HUMAN_ACTION_REQUIRED.")
        else:
            job.human_action_required = False
            job.checkpoint = None
            job.completed_at = datetime.now(timezone.utc)
            job.current_step = "COMPLETED" if result.status == JobStatus.COMPLETED.value else "FAILED"
            job.progress = 1.0 if result.status == JobStatus.COMPLETED.value else job.progress

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

    async def resume_job(
        self,
        job_id: str,
        db: Optional[AsyncSession] = None,
    ) -> CollectionResult:
        """
        Resumes a paused CollectionJob from its safe checkpoint after human completes verification.
        Only jobs in HUMAN_ACTION_REQUIRED state can be resumed.
        """
        job = await self.get_job(job_id=job_id, db=db)
        if not job:
            raise ValueError(f"CollectionJob with ID '{job_id}' not found.")

        if job.status != JobStatus.HUMAN_ACTION_REQUIRED.value:
            raise ValueError(
                f"Cannot resume job '{job_id}' because its status is '{job.status}'. "
                f"Only jobs in '{JobStatus.HUMAN_ACTION_REQUIRED.value}' state can be resumed."
            )

        # Transition to RESUMING
        job.status = JobStatus.RESUMING.value
        job.current_step = "RESUMING"
        job.human_action_required = False
        if db is not None:
            try:
                await db.commit()
            except Exception:
                await db.rollback()

        checkpoint = job.checkpoint or {}
        req_data = checkpoint.get("request") or job.collection_request
        request = CollectionRequest.model_validate(req_data)

        # Reconstruct sources to collect from checkpoint
        resume_sources: List[SourceDefinition] = []
        current_source_dict = checkpoint.get("current_source")
        if current_source_dict:
            resume_sources.append(SourceDefinition.model_validate(current_source_dict))

        remaining_sources_dicts = checkpoint.get("remaining_sources", [])
        for s_dict in remaining_sources_dicts:
            resume_sources.append(SourceDefinition.model_validate(s_dict))

        # If no sources recorded in checkpoint, fallback to selected_sources
        if not resume_sources and job.selected_sources:
            resume_sources = [SourceDefinition.model_validate(s) for s in job.selected_sources]

        # Retrieve documents already collected for this job
        existing_docs = await self.get_documents(job_id=job_id, limit=500, db=db)
        existing_doc_refs = [doc.to_reference() for doc in existing_docs]

        logger.info(
            f"Resuming CollectionJob '{job_id}' with {len(existing_doc_refs)} existing docs "
            f"and {len(resume_sources)} sources..."
        )

        job.status = JobStatus.RUNNING.value
        job.current_step = "SOURCE_COLLECTION"
        if db is not None:
            try:
                await db.commit()
            except Exception:
                await db.rollback()

        result = await self.manager.execute_job(
            request=request,
            sources=resume_sources,
            db=db,
            job_id=job.id,
            checkpoint=checkpoint,
            initial_documents=existing_doc_refs,
        )

        # Update final state
        job.status = result.status
        job.errors = result.errors
        job.metadata_.update(result.metadata.model_dump())

        if result.status == JobStatus.HUMAN_ACTION_REQUIRED.value:
            job.human_action_required = True
            job.human_action_reason = result.human_action_reason or "CAPTCHA_REQUIRED"
            job.checkpoint = result.checkpoint
            job.current_step = "HUMAN_ACTION_REQUIRED"
        elif result.status == JobStatus.COMPLETED.value:
            job.human_action_required = False
            job.checkpoint = None
            job.completed_at = datetime.now(timezone.utc)
            job.current_step = "COMPLETED"
            job.progress = 1.0
        else:
            job.human_action_required = False
            job.completed_at = datetime.now(timezone.utc)
            job.current_step = "FAILED"

        if result.errors:
            job.error = str(result.errors[0].get("error", "One or more errors occurred"))

        if db is not None:
            try:
                await db.commit()
                await db.refresh(job)
            except Exception as e:
                logger.warning(f"Could not update resumed job in DB: {e}")
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
