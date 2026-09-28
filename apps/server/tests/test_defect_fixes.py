"""
Regression tests for Phase 1-4 defect fixes.

Covers:
- Alternative-source discovery uses a correct, non-conflicting signature.
- Human-in-the-loop CAPTCHA resume cannot loop forever (attempt cap).
- Private/link-local/metadata hosts are blocked (SSRF).
- Non-2xx responses are not stored as valid raw documents.
- API pagination never emits conflicting page/offset parameters.
- The document cache is keyed by both request URL and canonical URL.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.collection.manager import CollectionManager
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.schemas import (
    CollectionRequest,
    CollectionStrategy,
    SourceDefinition,
    SourceType,
    AccessMethod,
    RawDocument,
    JobStatus,
)
from app.collection.collectors.base import CaptchaChallengeDetected, CollectorException
from app.collection.collectors.http import HTTPCollector
from app.collection.collectors.api import APICollector
from app.collection.policies import SourceAccessPolicy
from app.collection.management.cache import DocumentCache
from app.core.config import settings


# ---------------------------------------------------------------------------
# 1. Alternative-source fallback (previously raised TypeError)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_real_alternative_source_discovery_signature():
    """Calling discovery the way the manager does must not raise."""
    discovery = SourceDiscovery()
    failed = SourceDefinition(
        id="src_failed",
        name="Failed",
        base_url="https://www.linkedin.com/jobs/search",
        capabilities=["job_posting"],
    )
    req = CollectionRequest(objective="Find jobs", entity="job_posting", required_fields=["role"])

    alts = await discovery.discover_alternative_sources(
        failed, req, exclude_source_ids=["src_failed"]
    )
    assert isinstance(alts, list)
    assert all(a.source_id != "src_failed" for a in alts)


@pytest.mark.asyncio
async def test_captcha_zyte_unavailable_uses_real_alternative_discovery():
    """With Zyte disabled, a CAPTCHA must trigger real (unmocked) alternative discovery."""
    manager = CollectionManager()
    failed = SourceDefinition(
        id="src_blocked_real",
        name="Blocked",
        base_url="https://blocked-real.example",
        type=SourceType.WEBSITE,
        access_method=AccessMethod.HTTP,
        capabilities=["job_posting"],
    )
    req = CollectionRequest(
        objective="Find jobs",
        entity="job_posting",
        required_fields=["role"],
        collection_strategy=CollectionStrategy(allow_zyte=False, human_action_on_captcha=False),
    )

    async def always_captcha(src, *args, **kwargs):
        raise CaptchaChallengeDetected("challenge", url=src.base_url, source_id=src.id)

    with patch.object(manager.http_collector, "collect", side_effect=always_captcha):
        result = await manager.execute_job(request=req, sources=[failed])

    assert "src_blocked_real" in result.metadata.blocked_sources
    assert len(result.metadata.alternative_sources_used) > 0


# ---------------------------------------------------------------------------
# 2. Human-in-the-loop CAPTCHA resume cannot loop forever
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_captcha_attempt_cap_prevents_infinite_pause():
    manager = CollectionManager()
    src = SourceDefinition(
        id="src_cap",
        name="Cap",
        base_url="https://cap.example",
        type=SourceType.WEBSITE,
        access_method=AccessMethod.HTTP,
    )
    req = CollectionRequest(
        objective="Collect",
        entity="unmatched_entity_xyz",
        required_fields=["name"],
        collection_strategy=CollectionStrategy(human_action_on_captcha=True),
    )

    async def always_captcha(*args, **kwargs):
        raise CaptchaChallengeDetected("challenge", url=src.base_url, source_id=src.id)

    with patch.object(manager.http_collector, "collect", side_effect=always_captcha):
        checkpoint = None
        statuses = []
        # Feed each checkpoint back as if a human resumed the job repeatedly
        for _ in range(settings.DATAPILOT_MAX_HUMAN_ATTEMPTS + 3):
            result = await manager.execute_job(
                request=req, sources=[src], job_id="job_cap", checkpoint=checkpoint
            )
            statuses.append(result.status)
            checkpoint = result.checkpoint
            if result.status != JobStatus.HUMAN_ACTION_REQUIRED.value:
                break

    assert statuses.count(JobStatus.HUMAN_ACTION_REQUIRED.value) <= settings.DATAPILOT_MAX_HUMAN_ATTEMPTS
    assert statuses[-1] != JobStatus.HUMAN_ACTION_REQUIRED.value


# ---------------------------------------------------------------------------
# 3. SSRF protection
# ---------------------------------------------------------------------------

def test_ssrf_private_and_metadata_hosts_blocked():
    policy = SourceAccessPolicy()
    blocked = [
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/admin",
        "http://10.0.0.5/internal",
        "http://127.0.0.1:8000/secret",
        "http://[::1]/secret",
        "http://localhost/secret",
        "http://metadata.google.internal/computeMetadata/v1/",
    ]
    for url in blocked:
        ok, reason = policy.validate_url(url)
        assert ok is False, f"Expected {url} to be blocked ({reason})"

    ok, _ = policy.validate_url("https://example.com/startups")
    assert ok is True


# ---------------------------------------------------------------------------
# 4. Non-2xx responses are not stored as documents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_2xx_not_stored_as_document():
    collector = HTTPCollector()
    source = SourceDefinition(
        id="src_paywall",
        name="Paywalled",
        base_url="https://paywalled.example/article",
        type=SourceType.WEBSITE,
        access_method=AccessMethod.HTTP,
    )

    async def send(request, **kwargs):
        return httpx.Response(403, request=request, text="<html>Subscribers only</html>")

    with patch.object(collector.client, "send", side_effect=send):
        with pytest.raises(CollectorException):
            await collector.collect(source)


# ---------------------------------------------------------------------------
# 5. Pagination never emits conflicting page/offset params
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_pagination_no_conflicting_params():
    collector = APICollector()
    source = SourceDefinition(
        id="src_offset_api",
        name="Offset API",
        type=SourceType.API,
        base_url="https://api.example/v1/items",
        access_method=AccessMethod.API,
        metadata={"pagination": {"type": "offset_limit", "max_pages": 2}},
    )

    seen = []

    async def send(request, **kwargs):
        seen.append(request.url.params)
        return httpx.Response(200, request=request, json={"data": []})

    with patch.object(collector.client, "send", side_effect=send):
        await collector.collect(source, max_documents=3)

    assert seen, "expected at least one request"
    for params in seen:
        assert "page" not in params
        assert "offset" in params


# ---------------------------------------------------------------------------
# 6. Cache keyed by request URL and canonical URL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_when_base_url_differs_from_canonical():
    cache = DocumentCache()
    doc = RawDocument(
        document_id="doc_cache_1",
        source_id="src_1",
        url="https://example.com/page?ref=1",
        canonical_url="https://example.com/page",
        content="<html>x</html>",
    )
    await cache.set(doc.canonical_url, doc)

    assert await cache.get("https://example.com/page?ref=1") is not None
    assert await cache.get("https://example.com/page") is not None
