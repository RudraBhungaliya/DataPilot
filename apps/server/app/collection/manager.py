"""
Collection Manager.
Executes collection jobs, coordinates routing, retries, caching, rate limiting,
CAPTCHA detection, Zyte fallback, and alternative source fallback.
Supports partial success.
"""

import time
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.collection.schemas import (
    CollectionRequest,
    CollectionResult,
    CollectionMetadata,
    DocumentReference,
    SourceDefinition,
    SourceStatus,
    JobStatus,
)
from app.collection.router import SourceRouter
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.storage.document_store import RawDocumentStore
from app.collection.management.cache import DocumentCache
from app.collection.collectors.base import CaptchaChallengeDetected, CollectorException
from app.collection.collectors.zyte import ZyteAdapter
from app.services.email import email_service
from app.core.config import settings
from app.core.logger import logger


class CollectionManager:
    """
    Execution orchestrator for data collection jobs.
    """

    def __init__(
        self,
        router: Optional[SourceRouter] = None,
        discovery: Optional[SourceDiscovery] = None,
        document_store: Optional[RawDocumentStore] = None,
        cache: Optional[DocumentCache] = None,
        zyte_adapter: Optional[ZyteAdapter] = None,
    ):
        self.router = router or SourceRouter()
        self.http_collector = self.router.http_collector
        self.api_collector = self.router.api_collector
        self.discovery = discovery or SourceDiscovery()
        self.document_store = document_store or RawDocumentStore()
        self.cache = cache or DocumentCache()
        self.zyte_adapter = zyte_adapter or ZyteAdapter()

    async def _enqueue_alternative_sources(
        self,
        source: SourceDefinition,
        request: CollectionRequest,
        sources_queue: List[SourceDefinition],
        processed_source_ids: Set[str],
        blocked_source_ids: Set[str],
        alternative_sources_used: List[str],
    ) -> None:
        """Discovers replacement sources for a blocked/failed source and appends them to the queue."""
        try:
            alternatives = await self.discovery.discover_alternative_sources(
                failed_source=source,
                request=request,
                exclude_source_ids=list(processed_source_ids | blocked_source_ids),
            )
            for alt in alternatives:
                if alt.source_id not in processed_source_ids and alt not in sources_queue:
                    sources_queue.append(alt)
                    if alt.source_id not in alternative_sources_used:
                        alternative_sources_used.append(alt.source_id)
                    if alt.name not in alternative_sources_used:
                        alternative_sources_used.append(alt.name)
                    logger.info(f"Added alternative source to queue: {alt.name} ({alt.source_id})")
        except Exception as alt_err:
            logger.warning(f"Failed to find alternative sources: {alt_err}")

    async def execute_job(
        self,
        request: CollectionRequest,
        sources: List[SourceDefinition],
        db: Optional[AsyncSession] = None,
        job_id: Optional[str] = None,
        checkpoint: Optional[Dict[str, Any]] = None,
        initial_documents: Optional[List[DocumentReference]] = None,
        to_email: Optional[str] = None,
    ) -> CollectionResult:
        """
        Executes collection across the provided sources.
        When CAPTCHA challenges are detected:
        - NEVER bypasses, solves, or defeats CAPTCHA.
        - Captures a safe resume checkpoint.
        - Dispatches a human-intervention email to the configured recipient.
        - Enters HUMAN_ACTION_REQUIRED state so collection can safely resume.
        """
        start_time = time.monotonic()
        if not job_id:
            job_id = f"job_{request.request_id.replace('colreq_', '')}"

        # Human-in-the-loop attempt tracking (carried across resumes via the checkpoint)
        prior_attempts = 0
        if checkpoint:
            try:
                prior_attempts = int(checkpoint.get("resume_attempt", 0) or 0)
            except (TypeError, ValueError):
                prior_attempts = 0

        logger.info(
            f"Starting CollectionJob '{job_id}' for entity '{request.entity}' "
            f"across {len(sources)} sources (limit: {request.limits.max_documents} docs)"
        )

        documents: List[DocumentReference] = list(initial_documents or [])
        errors: List[Dict[str, Any]] = []
        processed_source_ids: Set[str] = set()
        blocked_source_ids: Set[str] = set()
        sources_used_ids: Set[str] = set()
        alternative_sources_used: List[str] = []
        zyte_used_count = 0
        failed_urls_count = 0
        last_successful_url: Optional[str] = None

        # Track URLs to prevent duplicate record collection upon resume
        collected_urls: Set[str] = {doc.url for doc in documents}
        if checkpoint and "collected_urls" in checkpoint:
            collected_urls.update(checkpoint["collected_urls"])

        # Sources queue allows dynamic appending of alternative sources
        sources_queue: List[SourceDefinition] = list(sources)
        queue_index = 0

        while queue_index < len(sources_queue):
            if len(documents) >= request.limits.max_documents:
                logger.info(f"Reached max_documents limit ({request.limits.max_documents}). Stopping collection.")
                break

            source = sources_queue[queue_index]
            queue_index += 1

            if source.source_id in processed_source_ids or source.source_id in blocked_source_ids:
                continue

            processed_source_ids.add(source.source_id)

            # 1. Check Document Cache
            cached_doc = await self.cache.get(source.base_url)
            if cached_doc:
                if cached_doc.url not in collected_urls:
                    logger.info(f"Retrieved document from cache for {source.base_url}")
                    doc_ref = await self.document_store.save(cached_doc, db=db)
                    documents.append(doc_ref)
                    collected_urls.add(cached_doc.url)
                    sources_used_ids.add(source.source_id)
                    last_successful_url = cached_doc.url
                continue

            # 2. Select Collector via Router
            collector = self.router.route(source)

            # 3. Collect from Source with CAPTCHA detection
            try:
                raw_docs = await collector.collect(source, request)
                for raw_doc in raw_docs:
                    # Prevent duplicate records on resume
                    if raw_doc.url in collected_urls or (raw_doc.canonical_url and raw_doc.canonical_url in collected_urls):
                        logger.info(f"Skipping duplicate document URL: {raw_doc.url}")
                        continue

                    raw_doc.job_id = job_id
                    # Cache document
                    await self.cache.set(raw_doc.canonical_url, raw_doc)
                    # Persist document
                    doc_ref = await self.document_store.save(raw_doc, db=db)
                    documents.append(doc_ref)
                    collected_urls.add(raw_doc.url)
                    if raw_doc.canonical_url:
                        collected_urls.add(raw_doc.canonical_url)
                    last_successful_url = raw_doc.url

                if raw_docs:
                    sources_used_ids.add(source.source_id)

            except CaptchaChallengeDetected as captcha_err:
                logger.warning(
                    f"CAPTCHA / Bot challenge detected at {source.base_url} ({source.source_id})."
                )

                # Strict Human-in-the-Loop policy: Never bypass, never solve.
                next_attempt = prior_attempts + 1
                max_attempts = settings.DATAPILOT_MAX_HUMAN_ATTEMPTS
                human_policy = request.collection_strategy.human_action_on_captcha

                if human_policy and next_attempt <= max_attempts:
                    logger.info(
                        f"Initiating human-in-the-loop handoff for job '{job_id}' on source "
                        f"'{source.name}' (attempt {next_attempt}/{max_attempts})."
                    )
                    remaining_sources_list = [
                        s.model_dump(mode="json") for s in sources_queue[queue_index:]
                    ]
                    checkpoint_data = {
                        "job_id": job_id,
                        "source_id": source.source_id,
                        "source_name": source.name,
                        "source_url": captcha_err.url or source.base_url,
                        "reason": "CAPTCHA_REQUIRED",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "current_step": "SOURCE_COLLECTION",
                        "current_page": 1,
                        "records_processed": len(documents),
                        "resume_attempt": next_attempt,
                        "max_human_attempts": max_attempts,
                        "collected_document_ids": [doc.document_id for doc in documents],
                        "collected_urls": list(collected_urls),
                        "last_successful_request": last_successful_url,
                        "remaining_sources": remaining_sources_list,
                        "current_source": source.model_dump(mode="json"),
                        "request": request.model_dump(mode="json"),
                    }

                    # Dispatch human action required email to configured client
                    target_email = to_email or settings.DATAPILOT_AUTH_EMAIL
                    await email_service.send_human_action_required_email(
                        to_email=target_email,
                        source_name=source.name,
                        source_url=captcha_err.url or source.base_url,
                        task_id=job_id,
                    )

                    duration_ms = int((time.monotonic() - start_time) * 1000)
                    metadata = CollectionMetadata(
                        sources_discovered=len(sources),
                        sources_used=len(sources_used_ids),
                        pages_collected=len(documents),
                        documents_collected=len(documents),
                        failed_urls=failed_urls_count,
                        duration_ms=duration_ms,
                        successful_sources=list(sources_used_ids),
                        failed_sources=[],
                    )

                    errors.append({
                        "source_id": source.source_id,
                        "url": captcha_err.url or source.base_url,
                        "error": "Source requires CAPTCHA verification before collection can continue.",
                        "reason": "CAPTCHA_REQUIRED",
                        "human_action_required": True,
                    })

                    return CollectionResult(
                        job_id=job_id,
                        request_id=request.request_id,
                        status=JobStatus.HUMAN_ACTION_REQUIRED.value,
                        documents=documents,
                        metadata=metadata,
                        errors=errors,
                        checkpoint=checkpoint_data,
                        human_action_required=True,
                        human_action_reason="CAPTCHA_REQUIRED",
                    )

                if human_policy:
                    logger.warning(
                        f"CAPTCHA on '{source.name}' unresolved after {max_attempts} human "
                        f"attempt(s). Marking source unavailable and continuing."
                    )

                # Fallback path if human action is explicitly disabled
                zyte_success = False
                is_zyte_ready = self.zyte_adapter.is_configured() if callable(self.zyte_adapter.is_configured) else bool(self.zyte_adapter.is_configured)
                if request.collection_strategy.allow_zyte and is_zyte_ready:
                    try:
                        zyte_docs = await self.zyte_adapter.collect(source, request)
                        for z_doc in zyte_docs:
                            if z_doc.url not in collected_urls:
                                z_doc.job_id = job_id
                                doc_ref = await self.document_store.save(z_doc, db=db)
                                documents.append(doc_ref)
                                collected_urls.add(z_doc.url)
                                last_successful_url = z_doc.url

                        if zyte_docs:
                            sources_used_ids.add(source.source_id)
                            zyte_used_count += len(zyte_docs)
                            zyte_success = True
                            logger.info(f"Zyte fallback succeeded for {source.base_url}")
                    except Exception as zyte_err:
                        logger.warning(f"Zyte fallback also failed for {source.base_url}: {zyte_err}")
                        errors.append({
                            "source_id": source.source_id,
                            "url": source.base_url,
                            "error": f"CAPTCHA encountered and Zyte fallback failed: {str(zyte_err)}",
                            "zyte_attempted": True,
                        })

                if not zyte_success:
                    blocked_source_ids.add(source.source_id)
                    source.status = SourceStatus.BLOCKED
                    self.discovery.registry.mark_blocked(source.source_id)
                    failed_urls_count += 1

                    if not any(e.get("source_id") == source.source_id for e in errors):
                        errors.append({
                            "source_id": source.source_id,
                            "url": source.base_url,
                            "error": "CAPTCHA challenge detected; source marked unavailable.",
                            "zyte_attempted": is_zyte_ready,
                        })

                    # Discover alternative sources to replace the blocked source
                    logger.info(
                        f"Discovering alternative sources to substitute blocked source '{source.name}'..."
                    )
                    await self._enqueue_alternative_sources(
                        source,
                        request,
                        sources_queue,
                        processed_source_ids,
                        blocked_source_ids,
                        alternative_sources_used,
                    )


            except CollectorException as ce:
                logger.warning(f"Collection error on {source.name}: {ce}")
                failed_urls_count += 1
                errors.append({
                    "source_id": source.source_id,
                    "url": ce.url,
                    "status_code": ce.status_code,
                    "error": str(ce),
                })

            except Exception as e:
                logger.error(f"Unexpected error collecting from {source.name}: {e}", exc_info=True)
                failed_urls_count += 1
                errors.append({
                    "source_id": source.source_id,
                    "url": source.base_url,
                    "error": str(e),
                })

        # 7. Finalize Job Status
        duration_ms = int((time.monotonic() - start_time) * 1000)

        if len(documents) > 0:
            final_status = JobStatus.COMPLETED.value
        else:
            final_status = JobStatus.FAILED.value

        metadata = CollectionMetadata(
            sources_discovered=len(sources),
            sources_used=len(sources_used_ids),
            pages_collected=len(documents),
            documents_collected=len(documents),
            failed_urls=failed_urls_count,
            duration_ms=duration_ms,
            zyte_used=(zyte_used_count > 0),
            zyte_used_count=zyte_used_count,
            alternative_sources_used=alternative_sources_used,
            blocked_sources=list(blocked_source_ids),
            inaccessible_sources=list(blocked_source_ids),
            successful_sources=list(sources_used_ids),
            failed_sources=[e.get("source_id") for e in errors if e.get("source_id")],
        )

        logger.info(
            f"CollectionJob '{job_id}' completed with status {final_status} "
            f"({len(documents)} documents, {failed_urls_count} failed, {duration_ms}ms)"
        )

        return CollectionResult(
            job_id=job_id,
            request_id=request.request_id,
            status=final_status,
            documents=documents,
            metadata=metadata,
            errors=errors,
        )

    execute_collection = execute_job

    async def aclose(self) -> None:
        """Closes collector network resources held by this manager."""
        try:
            await self.router.aclose()
        except Exception:
            pass
