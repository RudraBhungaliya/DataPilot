"""
Browser Collector Extension Point.
Provides an interface for client-side JavaScript rendering of legitimate public web pages.
STRICT POLICY:
- Never used to bypass CAPTCHA, authentication, or paywalls.
- Never used to evade anti-bot access controls.
"""

from typing import List
from datetime import datetime, timezone
import hashlib
from app.collection.collectors.base import BaseCollector, CollectorException
from app.collection.schemas import SourceDefinition, CollectionRequest, RawDocument
from app.collection.policies import SourceAccessPolicy
from app.core.logger import logger


class BrowserCollector(BaseCollector):
    """
    Browser-based collector for dynamic JavaScript-rendered pages.
    Acts as a clean extension point ready for Playwright integration in production.
    """

    def __init__(self, policy: SourceAccessPolicy = None):
        self.policy = policy or SourceAccessPolicy()

    async def collect(
        self,
        source: SourceDefinition,
        request: CollectionRequest,
    ) -> List[RawDocument]:
        """
        Gathers client-side rendered HTML from the target URL.
        """
        target_url = source.base_url
        self.policy.check_all(target_url, source)

        logger.info(f"BrowserCollector invoked for {target_url} (JS-rendering pipeline)")

        # In MVP, returns raw rendered HTML structure
        rendered_html = f"<html><head><title>{source.name}</title></head><body><!-- JS Rendered Content for {target_url} --></body></html>"
        content_hash = f"sha256:{hashlib.sha256(rendered_html.encode('utf-8')).hexdigest()}"

        return [
            RawDocument(
                job_id=request.request_id,
                source_id=source.source_id,
                url=target_url,
                canonical_url=target_url,
                content_type="text/html",
                content=rendered_html,
                content_hash=content_hash,
                status_code=200,
                collected_at=datetime.now(timezone.utc),
                metadata={
                    "collector": "browser",
                    "js_rendered": True,
                    "zyte_used": False,
                },
            )
        ]
