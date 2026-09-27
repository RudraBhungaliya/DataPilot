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

    async def execute_job(
        self,
        request: CollectionRequest,
        sources: List[SourceDefinition],
        db: Optional[AsyncSession] = None,
    ) -> CollectionResult:
        """
        Executes collection across the provided sources.
        Handles CAPTCHA barriers via Zyte (if configured) or pivots to alternative sources.
        """
        start_time = time.monotonic()
        job_id = f"job_{request.request_id.replace('colreq_', '')}"

        logger.info(
            f"Starting CollectionJob '{job_id}' for entity '{request.entity}' "
            f"across {len(sources)} initial sources (limit: {request.limits.max_documents} docs)"
        )

        documents: List[DocumentReference] = []
        errors: List[Dict[str, Any]] = []
        processed_source_ids: Set[str] = set()
        blocked_source_ids: Set[str] = set()
        sources_used_ids: Set[str] = set()
        alternative_sources_used: List[str] = []
        zyte_used_count = 0
        failed_urls_count = 0

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
                logger.info(f"Retrieved document from cache for {source.base_url}")
                doc_ref = await self.document_store.save(cached_doc, db=db)
                documents.append(doc_ref)
                sources_used_ids.add(source.source_id)
                continue

            # 2. Select Collector via Router
            collector = self.router.route(source)

            # 3. Collect from Source with CAPTCHA & Fallback handling
            try:
                raw_docs = await collector.collect(source, request)
                for raw_doc in raw_docs:
                    raw_doc.job_id = job_id
                    # Cache document
                    await self.cache.set(raw_doc.canonical_url, raw_doc)
                    # Persist document
                    doc_ref = await self.document_store.save(raw_doc, db=db)
                    documents.append(doc_ref)

                if raw_docs:
                    sources_used_ids.add(source.source_id)

            except CaptchaChallengeDetected as captcha_err:
                logger.warning(
                    f"CAPTCHA / Bot challenge detected at {source.base_url} ({source.source_id}). "
                    f"Evaluating Zyte fallback policy..."
                )

                zyte_success = False

                # 4. Check Zyte Adapter fallback
                is_zyte_ready = self.zyte_adapter.is_configured() if callable(self.zyte_adapter.is_configured) else bool(self.zyte_adapter.is_configured)
                if request.collection_strategy.allow_zyte and is_zyte_ready:
                    try:
                        zyte_docs = await self.zyte_adapter.collect(source, request)
                        for z_doc in zyte_docs:
                            z_doc.job_id = job_id
                            doc_ref = await self.document_store.save(z_doc, db=db)
                            documents.append(doc_ref)

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
                    # 5. Zyte not configured or Zyte failed -> STOP accessing source -> Mark BLOCKED
                    blocked_source_ids.add(source.source_id)
                    source.status = SourceStatus.BLOCKED
                    self.discovery.registry.mark_blocked(source.source_id)
                    failed_urls_count += 1

                    zyte_cfg = self.zyte_adapter.is_configured() if callable(self.zyte_adapter.is_configured) else bool(self.zyte_adapter.is_configured)
                    if not any(e.get("source_id") == source.source_id for e in errors):
                        errors.append({
                            "source_id": source.source_id,
                            "url": source.base_url,
                            "error": "CAPTCHA challenge detected; Zyte unavailable or failed. Source marked unavailable.",
                            "zyte_attempted": zyte_cfg,
                        })

                    # 6. Discover Alternative Sources to replace blocked source
                    logger.info(
                        f"Discovering alternative sources to substitute blocked source '{source.name}'..."
                    )
                    try:
                        alternatives = await self.discovery.discover_alternative_sources(
                            source,
                            request,
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
