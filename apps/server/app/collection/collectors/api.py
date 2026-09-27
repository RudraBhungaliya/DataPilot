"""
Generic Public API Collector.
Fetches structured JSON data from external public REST APIs.
Supports query parameter templating, pagination, retries, and rate limiting.
"""

import httpx
import hashlib
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from app.collection.collectors.base import BaseCollector, CollectorException
from app.collection.schemas import SourceDefinition, CollectionRequest, RawDocument
from app.collection.policies import SourceAccessPolicy
from app.collection.management.rate_limit import RateLimiter
from app.collection.management.retry import RetryHandler
from app.collection.management.pagination import PaginationHandler
from app.core.config import settings
from app.core.logger import logger


class APICollector(BaseCollector):
    """
    Collector for REST APIs and structured JSON endpoints.
    """

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        policy: Optional[SourceAccessPolicy] = None,
        rate_limiter: Optional[RateLimiter] = None,
        retry_handler: Optional[RetryHandler] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.client = client or httpx.AsyncClient(
            timeout=float(timeout_seconds if timeout_seconds is not None else settings.DATAPILOT_HTTP_TIMEOUT),
            follow_redirects=True,
            headers={"User-Agent": settings.DATAPILOT_HTTP_USER_AGENT, "Accept": "application/json"},
        )
        self.policy = policy or SourceAccessPolicy()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_handler = retry_handler or RetryHandler()

    def _build_query_params(self, source: SourceDefinition, request: CollectionRequest) -> Dict[str, Any]:
        """
        Derives query parameters from request constraints and source configuration.
        """
        params: Dict[str, Any] = {}
        # Default query token from entity or constraint
        if request and request.entity:
            params["q"] = request.entity

        if request and request.constraints:
            for k, v in request.constraints.items():
                if isinstance(v, (str, int, float, bool)):
                    params[k] = v

        # Source metadata defaults override
        if "default_params" in source.metadata and isinstance(source.metadata["default_params"], dict):
            params.update(source.metadata["default_params"])

        return params

    async def collect(
        self,
        source: SourceDefinition,
        request: Optional[CollectionRequest] = None,
        max_documents: Optional[int] = None,
    ) -> List[RawDocument]:
        """
        Gathers raw JSON documents from the API source, handling pagination if configured.
        """
        target_url = source.base_url
        self.policy.check_all(target_url, source)

        domain = source.domain or "default"
        client = self.client
        req_id = request.request_id if request else f"colreq_{source.source_id}"
        max_docs = max_documents or (request.limits.max_documents if request and request.limits else 100)

        collected_docs: List[RawDocument] = []
        pag_cfg = source.metadata.get("pagination", {}) if isinstance(source.metadata.get("pagination"), dict) else {}
        pagination_type = pag_cfg.get("type", source.metadata.get("pagination_type", "page_number"))
        page_param = pag_cfg.get("page_param", "page")
        page_size = pag_cfg.get("page_size", source.metadata.get("page_size", 20))
        max_pages = pag_cfg.get("max_pages", source.metadata.get("max_pages", 2))

        base_params = self._build_query_params(source, request) if request else {}
        current_page = 0
        current_url = target_url

        while current_page < max_pages and len(collected_docs) < max_docs:
            # Prepare page parameters
            page_params = base_params.copy()
            page_params[page_param] = current_page + 1

            pag_params = PaginationHandler.get_next_request_params(
                strategy=pagination_type,
                current_page=current_page,
                page_size=page_size,
                config=pag_cfg or source.metadata,
            )
            page_params.update(pag_params)

            async def _fetch():
                async with self.rate_limiter.acquire_context(domain, source.rate_limit):
                    logger.debug(f"API GET {current_url} params={page_params}")
                    req = client.build_request("GET", current_url, params=page_params)
                    resp = await client.send(req)

                    if resp.status_code == 404:
                        raise CollectorException("Endpoint not found (404)", source.source_id, current_url, status_code=404)
                    if resp.status_code >= 500:
                        raise httpx.HTTPStatusError(f"API Server Error {resp.status_code}", request=req, response=resp)

                    return resp

            def is_retryable(e: Exception) -> bool:
                if isinstance(e, CollectorException):
                    return False
                return True

            response = await self.retry_handler.execute(_fetch, is_retryable=is_retryable)

            # Store raw document
            content = response.text
            content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

            doc_id = f"doc_api_{source.source_id}_{current_page + 1}"
            raw_doc = RawDocument(
                document_id=doc_id,
                job_id=req_id,
                source_id=source.source_id,
                url=str(response.url),
                canonical_url=str(response.url),
                content_type="application/json",
                content=content,
                content_hash=content_hash,
                status_code=response.status_code,
                collected_at=datetime.now(timezone.utc),
                metadata={
                    "collector": "api",
                    "page": current_page + 1,
                    "source_name": source.name,
                    "zyte_used": False,
                },
            )
            collected_docs.append(raw_doc)
            current_page += 1

            # Check if next URL exists in response
            try:
                res_json = response.json()
                next_url = PaginationHandler.extract_next_url(res_json, dict(response.headers), source.metadata)
                if next_url:
                    current_url = next_url
                elif isinstance(res_json, dict):
                    tot = res_json.get("total_pages")
                    if tot is not None and current_page >= tot:
                        break
                    res_items = res_json.get("results") or res_json.get("items") or res_json.get("data")
                    if isinstance(res_items, list) and len(res_items) == 0:
                        break
                elif isinstance(res_json, list) and len(res_json) == 0:
                    break
            except Exception:
                break

        logger.info(f"API Collector retrieved {len(collected_docs)} documents from {source.name}")
        return collected_docs
