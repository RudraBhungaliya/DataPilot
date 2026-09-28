"""
Zyte Provider Adapter.
Optional external proxy/extractor adapter used ONLY when configured and normal collection
encounters an authorized access barrier (e.g. Cloudflare / CAPTCHA).
STRICT POLICY:
- Never used as default collector.
- If Zyte fails or is unconfigured, system halts access to the blocked source and discovers alternative sources.
"""

import httpx
import base64
import hashlib
from typing import List, Optional
from datetime import datetime, timezone
from app.collection.collectors.base import BaseCollector, CollectorException
from app.collection.schemas import SourceDefinition, CollectionRequest, RawDocument
from app.core.config import settings
from app.core.logger import logger


class ZyteAdapter(BaseCollector):
    """
    Optional external adapter for Zyte API.
    """

    def __init__(self, api_key: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        self.api_key = api_key or settings.ZYTE_API_KEY
        self.api_url = settings.ZYTE_API_URL
        self.client = client

    def is_configured(self) -> bool:
        """Checks if Zyte credentials are provided in environment settings."""
        return bool(self.api_key and self.api_key.strip())

    async def aclose(self) -> None:
        """Closes the adapter's client if one was supplied."""
        if self.client is not None:
            try:
                await self.client.aclose()
            except Exception:
                pass

    async def collect(
        self,
        source: SourceDefinition,
        request: CollectionRequest,
    ) -> List[RawDocument]:
        """
        Executes fallback request through Zyte API.
        """
        if not self.is_configured():
            raise CollectorException(
                "Zyte adapter is not configured (missing ZYTE_API_KEY)",
                source.source_id,
                source.base_url,
                status_code=503,
            )

        target_url = source.base_url
        logger.info(f"ZyteAdapter fallback initiated for {target_url} (source: {source.source_id})")

        auth = (self.api_key, "")
        payload = {
            "url": target_url,
            "httpResponseBody": True,
        }

        should_close = False
        client = self.client
        if not client:
            client = httpx.AsyncClient(timeout=float(settings.DATAPILOT_HTTP_TIMEOUT))
            should_close = True

        try:
            resp = await client.post(self.api_url, auth=auth, json=payload)
            if resp.status_code != 200:
                raise CollectorException(
                    f"Zyte API returned error {resp.status_code}: {resp.text[:200]}",
                    source.source_id,
                    target_url,
                    status_code=resp.status_code,
                )

            data = resp.json()
            raw_body_b64 = data.get("httpResponseBody")
            if raw_body_b64:
                content = base64.b64decode(raw_body_b64).decode("utf-8", errors="replace")
            else:
                content = data.get("browserHtml", "")

            content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

            raw_doc = RawDocument(
                job_id=request.request_id,
                source_id=source.source_id,
                url=target_url,
                canonical_url=target_url,
                content_type="text/html",
                content=content,
                content_hash=content_hash,
                status_code=resp.status_code,
                collected_at=datetime.now(timezone.utc),
                metadata={
                    "collector": "zyte",
                    "zyte_used": True,
                    "original_collector": "http",
                },
            )

            logger.info(f"ZyteAdapter successfully retrieved {target_url}")
            return [raw_doc]

        finally:
            if should_close:
                await client.aclose()
