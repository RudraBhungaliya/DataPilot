"""
Async HTTP Collector.
Gathers public web documents using httpx connection pooling, rate limiting, and CAPTCHA detection.
Does not perform semantic parsing. Stores raw payloads only.
"""

import httpx
import hashlib
from typing import List, Optional
from datetime import datetime, timezone
from app.collection.collectors.base import BaseCollector, CollectorException, CaptchaChallengeDetected
from app.collection.schemas import SourceDefinition, CollectionRequest, RawDocument
from app.collection.policies import SourceAccessPolicy
from app.collection.management.rate_limit import RateLimiter
from app.collection.management.retry import RetryHandler
from app.core.config import settings
from app.core.logger import logger


class HTTPCollector(BaseCollector):
    """
    Standard HTTP/HTTPS collector for normal public websites.
    """

    # Strong interstitial phrases that reliably indicate an anti-bot challenge page.
    CAPTCHA_STRONG_SIGNALS = [
        "cf-chl",
        "challenge-running",
        "please verify you are a human",
        "verify you are human",
        "just a moment",
        "checking your browser",
        "attention required! | cloudflare",
        "access denied - security check",
        "security check to continue",
        "enable javascript and cookies to continue",
        "robot or human?",
        "ddos-guard",
        "perimeterx",
        "px-captcha",
        "are you a robot",
    ]
    # Weak widget markers that only count when paired with a challenge HTTP status.
    CAPTCHA_WIDGET_SIGNALS = ["recaptcha", "g-recaptcha", "hcaptcha", "captcha"]

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        policy: Optional[SourceAccessPolicy] = None,
        rate_limiter: Optional[RateLimiter] = None,
        retry_handler: Optional[RetryHandler] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ):
        self.client = client or httpx.AsyncClient(
            timeout=float(settings.DATAPILOT_HTTP_TIMEOUT),
            follow_redirects=True,
            headers={"User-Agent": settings.DATAPILOT_HTTP_USER_AGENT},
        )
        self.policy = policy or SourceAccessPolicy()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_handler = retry_handler or RetryHandler(
            max_retries=max_retries if max_retries is not None else settings.DATAPILOT_HTTP_MAX_RETRIES,
            initial_delay=retry_delay if retry_delay is not None else 0.5,
        )
        self.max_size_bytes = settings.DATAPILOT_MAX_DOCUMENT_SIZE_MB * 1024 * 1024

    def is_captcha_challenge(
        self,
        status_code: int,
        headers: httpx.Headers,
        body_text: str,
        content_type: str = "",
    ) -> bool:
        """
        Determines whether a response is an anti-bot/CAPTCHA challenge page.

        A page that merely *embeds* a CAPTCHA widget (e.g. a contact form or an invisible
        reCAPTCHA v3 script) is NOT a challenge and must not be treated as one. Only
        explicit WAF headers, strong interstitial phrases, or weak widget markers paired
        with a challenge HTTP status qualify as a challenge.
        """
        # 1. Explicit WAF / challenge response headers
        if "cf-mitigated" in headers or "x-amzn-waf-action" in headers:
            return True

        server = (headers.get("server") or "").lower()
        is_waf_server = any(
            waf in server for waf in ("cloudflare", "akamai", "sucuri", "imperva")
        )

        # Only HTML/text bodies are scanned, and only the first 200 KB
        ct = (content_type or "").lower()
        body_is_scannable = (not ct) or ("html" in ct) or ("text" in ct)
        if not (body_is_scannable and body_text):
            return False

        lower_body = body_text[:200_000].lower()

        # 2. Strong interstitial phrases always indicate a challenge
        if any(sig in lower_body for sig in self.CAPTCHA_STRONG_SIGNALS):
            return True

        # 3. Weak widget markers only count on a challenge status or WAF-fronted server
        if (status_code in (401, 403, 429, 503) or is_waf_server) and any(
            sig in lower_body for sig in self.CAPTCHA_WIDGET_SIGNALS
        ):
            return True

        return False

    async def collect(
        self,
        source: SourceDefinition,
        request: Optional[CollectionRequest] = None,
    ) -> List[RawDocument]:
        """
        Collects raw document from source base URL or configured endpoints.
        """
        target_url = source.base_url
        self.policy.check_all(target_url, source)

        domain = source.domain or "default"
        client = self.client
        job_id = request.request_id if request else f"col_{source.source_id}"

        async def _fetch():
            # Apply rate limiting
            async with self.rate_limiter.acquire_context(domain, source.rate_limit):
                logger.debug(f"HTTP GET {target_url} (source: {source.source_id})")
                req = client.build_request("GET", target_url)
                resp = await client.send(req)

                # Enforce max document size
                if len(resp.content) > self.max_size_bytes:
                    raise CollectorException(
                        f"Response size ({len(resp.content)} bytes) exceeds max permitted size",
                        source.source_id,
                        target_url,
                        status_code=resp.status_code,
                    )

                # Check for CAPTCHA / bot challenge barrier
                body_text = resp.text
                content_type = resp.headers.get("content-type", "")
                if self.is_captcha_challenge(resp.status_code, resp.headers, body_text, content_type):
                    logger.warning(
                        f"CAPTCHA / Bot challenge detected at {target_url}. Policy forbids bypass."
                    )
                    raise CaptchaChallengeDetected(
                        message="Cloudflare/Anti-bot CAPTCHA challenge encountered",
                        source_id=source.source_id,
                        url=target_url,
                    )

                # Retryable transient failures: server errors and rate limiting
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise httpx.HTTPStatusError(
                        f"Transient HTTP error {resp.status_code}",
                        request=req,
                        response=resp,
                    )

                # 404 is a permanent, non-retryable failure
                if resp.status_code == 404:
                    raise CollectorException(
                        "Resource not found (404)",
                        source.source_id,
                        target_url,
                        status_code=404,
                    )

                # Any other non-2xx (401, 403 non-CAPTCHA, 410, ...) is a permanent failure
                if resp.status_code >= 400:
                    raise CollectorException(
                        f"HTTP {resp.status_code} response",
                        source.source_id,
                        target_url,
                        status_code=resp.status_code,
                    )

                return resp

        def is_retryable(e: Exception) -> bool:
            # Never retry CAPTCHAs, 404s, or policy denials
            if isinstance(e, (CaptchaChallengeDetected, CollectorException)):
                return False
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                return False
            return True

        response = await self.retry_handler.execute(_fetch, is_retryable=is_retryable)

        # Package raw document
        content_type = response.headers.get("content-type", "text/html").split(";")[0].strip()
        content = response.text
        content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

        raw_doc = RawDocument(
            job_id=job_id,
            source_id=source.source_id,
            url=target_url,
            canonical_url=str(response.url),
            content_type=content_type,
            content=content,
            content_hash=content_hash,
            status_code=response.status_code,
            collected_at=datetime.now(timezone.utc),
            metadata={
                "collector": "http",
                "response_headers": dict(response.headers),
                "size_bytes": len(response.content),
                "zyte_used": False,
            },
        )

        logger.info(f"HTTP Collector retrieved {target_url} ({len(response.content)} bytes)")
        return [raw_doc]
