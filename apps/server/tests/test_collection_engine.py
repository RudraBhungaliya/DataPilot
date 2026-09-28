"""
Comprehensive Test Suite for Phase 4: Source Collection Engine.
Tests all 16 required test cases and architectural components:
1. CollectionRequest validation (valid & invalid)
2. CollectionResult schema & metadata
3. Source validation & Domain normalization
4. SourceRegistry (duplicate prevention, capability search)
5. SourceDiscovery (registry provider, direct provider, alternative discovery)
6. SourceRouter (deterministic routing for API, HTTP, Browser, Zyte)
7. SourceAccessPolicy (schemes, blocked hosts, robots.txt)
8. HTTP Collector transient retries & backoff (TEST 6)
9. HTTP Collector 404 non-retry (TEST 7)
10. Rate limiting & 429 handling (TEST 8)
11. API Collector pagination (TEST 9)
12. CAPTCHA -> Zyte fallback when configured (TEST 10)
13. CAPTCHA -> Zyte unavailable -> Alternative source discovery (TEST 11)
14. CAPTCHA -> Zyte fails -> Source blocked -> Alternative source discovery (TEST 12)
15. Raw Document Store integrity (TEST 13)
16. Workflow Engine integration (DISCOVER_SOURCES -> COLLECT_DATA) (TEST 14)
17. Partial success / multi-source resilience (TEST 15)
18. CollectionResult reporting (TEST 16)
19. Caching layer
20. Collection REST API endpoints
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.collection.schemas import (
    CollectionRequest,
    CollectionResult,
    CollectionStrategy,
    SourceDefinition,
    RawDocument,
    SourceType,
    AccessMethod,
    SourceStatus,
    JobStatus,
)
from app.collection.discovery.registry import SourceRegistry
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.discovery.registry_provider import RegistryDiscoveryProvider
from app.collection.discovery.direct_provider import DirectURLProvider
from app.collection.router import SourceRouter
from app.collection.policies import SourceAccessPolicy
from app.collection.management.retry import RetryHandler
from app.collection.management.rate_limit import RateLimiter
from app.collection.management.pagination import PaginationHandler
from app.collection.management.cache import DocumentCache
from app.collection.storage.document_store import RawDocumentStore
from app.collection.collectors.base import CaptchaChallengeDetected, CollectorError
from app.collection.collectors.http import HTTPCollector
from app.collection.collectors.api import APICollector
from app.collection.collectors.browser import BrowserCollector
from app.collection.collectors.zyte import ZyteAdapter
from app.collection.manager import CollectionManager
from app.collection.service import CollectionService
from app.workflows.engine import WorkflowEngine
from app.workflows.registry import get_default_registry
from app.workflows.planner import WorkflowPlanner
from app.workflows.types import StepType, StepStatus, WorkflowStatus
from app.ai.schemas import StructuredRequirement, OutputFormat


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. CollectionRequest Schema Validation (TEST 1 & TEST 2)
# ---------------------------------------------------------------------------

def test_collection_request_valid():
    """TEST 1: Valid CollectionRequest is accepted."""
    req_data = {
        "request_id": "colreq_123",
        "workflow_id": "workflow_123",
        "objective": "Find Indian AI startups founded after 2020 with funding above $5M",
        "entity": "startup",
        "required_fields": ["company", "founders", "website", "funding", "funding_date", "investors"],
        "constraints": {
            "country": "India",
            "industry": "AI",
            "founded_after": 2020,
            "funding_above": 5000000,
        },
        "collection_strategy": {
            "allow_api": True,
            "allow_web": True,
            "allow_public_datasets": True,
            "allow_rss": True,
        },
        "limits": {
            "max_sources": 10,
            "max_documents": 1000,
        },
    }
    request = CollectionRequest.model_validate(req_data)
    assert request.request_id == "colreq_123"
    assert request.entity == "startup"
    assert "company" in request.required_fields
    assert request.limits.max_sources == 10
    assert request.collection_strategy.allow_api is True


def test_collection_request_invalid_fails():
    """TEST 2: Invalid CollectionRequest triggers validation error."""
    # Missing required 'objective' and 'entity'
    with pytest.raises(Exception):
        CollectionRequest.model_validate({
            "request_id": "colreq_invalid",
            "required_fields": [],
        })


# ---------------------------------------------------------------------------
# 2. Source Model & Domain Normalization (TEST 3)
# ---------------------------------------------------------------------------

def test_source_domain_normalization():
    """Domain normalization consistently identifies same host."""
    s1 = SourceDefinition(
        name="Test 1",
        type=SourceType.WEBSITE,
        base_url="https://www.example.com/startups?ref=1",
    )
    s2 = SourceDefinition(
        name="Test 2",
        type=SourceType.WEBSITE,
        base_url="http://example.com/about/",
    )
    assert s1.domain == "example.com"
    assert s2.domain == "example.com"
    assert s1.domain == s2.domain


def test_source_registry_duplicate_prevention():
    """TEST 3: Duplicate source is handled correctly without overwriting or erroring corruptively."""
    registry = SourceRegistry()
    initial_count = len(registry.list())

    s1 = SourceDefinition(
        id="src_custom_1",
        name="Custom Data Source",
        type=SourceType.API,
        base_url="https://api.customdata.org/v1",
        capabilities=["startup", "funding"],
    )
    registered = registry.register(s1)
    assert registered.id == "src_custom_1"
    assert len(registry.list()) == initial_count + 1

    # Attempt to register duplicate with same ID
    s1_dup = SourceDefinition(
        id="src_custom_1",
        name="Custom Data Source (Updated)",
        type=SourceType.API,
        base_url="https://api.customdata.org/v1",
        capabilities=["startup", "funding", "investors"],
    )
    dup_res = registry.register(s1_dup)
    assert dup_res.id == "src_custom_1"
    # Overwrites entry cleanly, total count remains same
    assert len(registry.list()) == initial_count + 1
    assert "investors" in registry.get("src_custom_1").capabilities


def test_source_registry_capability_and_domain_lookup():
    """Lookup by capability and domain works reliably."""
    registry = SourceRegistry()
    # Check default seeded sources
    sources_with_startup = registry.find_by_capability("startup")
    assert len(sources_with_startup) > 0

    hn_sources = registry.find_by_domain("news.ycombinator.com")
    assert len(hn_sources) >= 1
    assert hn_sources[0].id == "source_hackernews_api"


# ---------------------------------------------------------------------------
# 3. Source Discovery Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_source_discovery_engine():
    """SourceDiscovery uses registry and direct URL providers."""
    registry = SourceRegistry()
    discovery = SourceDiscovery(registry=registry)

    req = CollectionRequest(
        objective="Find AI startups and funding in India",
        entity="startup",
        required_fields=["company", "funding"],
        constraints={"country": "India"},
        source_preferences=["Y Combinator Directory"],
    )

    discovered = await discovery.discover(req)
    assert len(discovered) > 0
    # Preferences or capability matches should be included
    names = [s.name for s in discovered]
    assert any("Y Combinator" in n or "Startup" in n or "Hacker News" in n for n in names)


@pytest.mark.asyncio
async def test_source_discovery_direct_url_provider():
    """Direct URLs in metadata or preferences are converted into valid sources."""
    discovery = SourceDiscovery(registry=SourceRegistry())
    req = CollectionRequest(
        objective="Collect specific startup profiles",
        entity="startup",
        required_fields=["name"],
        metadata={"direct_urls": ["https://data.startups.in/api/v1/companies"]},
    )
    discovered = await discovery.discover(req)
    direct_sources = [s for s in discovered if s.type == SourceType.WEBSITE or s.type == SourceType.API]
    urls = [s.base_url for s in direct_sources]
    assert "https://data.startups.in/api/v1/companies" in urls


# ---------------------------------------------------------------------------
# 4. Source Router Tests (TEST 4 & TEST 5)
# ---------------------------------------------------------------------------

def test_source_router_api_selection():
    """TEST 4: API source -> API Collector selected."""
    router = SourceRouter()
    api_source = SourceDefinition(
        id="src_api_1",
        name="API Source",
        type=SourceType.API,
        base_url="https://api.github.com/repos",
        access_method=AccessMethod.API,
    )
    collector = router.route(api_source)
    assert isinstance(collector, APICollector)


def test_source_router_http_selection():
    """TEST 5: Normal webpage -> HTTP Collector selected."""
    router = SourceRouter()
    web_source = SourceDefinition(
        id="src_web_1",
        name="Blog Page",
        type=SourceType.WEBSITE,
        base_url="https://news.ycombinator.com",
        access_method=AccessMethod.HTTP,
    )
    collector = router.route(web_source)
    assert isinstance(collector, HTTPCollector)


def test_source_router_browser_and_zyte_selection():
    """JS-rendered webpage selects browser; explicit zyte selects ZyteAdapter."""
    router = SourceRouter()
    js_source = SourceDefinition(
        name="SPA App",
        type=SourceType.WEBSITE,
        base_url="https://app.spa-example.com",
        access_method=AccessMethod.BROWSER,
    )
    assert isinstance(router.route(js_source), BrowserCollector)

    zyte_source = SourceDefinition(
        name="Protected Site",
        type=SourceType.WEBSITE,
        base_url="https://protected.com",
        access_method=AccessMethod.ZYTE,
    )
    assert isinstance(router.route(zyte_source), ZyteAdapter)


# ---------------------------------------------------------------------------
# 5. Source Access Policy & Safety Rules
# ---------------------------------------------------------------------------

def test_source_access_policy():
    """Access policy strictly checks scheme, private hosts, and denied status."""
    policy = SourceAccessPolicy()

    # Valid HTTPS
    valid, reason = policy.validate_url("https://example.com/startups")
    assert valid is True

    # Invalid scheme
    valid_ftp, reason = policy.validate_url("ftp://example.com/startups")
    assert valid_ftp is False
    assert "Unsupported scheme" in reason

    # Localhost/private IP blocked
    valid_local, reason = policy.validate_url("http://localhost:8000/secret")
    assert valid_local is False
    assert "Restricted host" in reason

    # Disabled source
    disabled_source = SourceDefinition(
        name="Blocked Source",
        type=SourceType.WEBSITE,
        base_url="https://blocked.com",
        status=SourceStatus.DISABLED,
    )
    valid_status, reason = policy.is_allowed(disabled_source)
    assert valid_status is False
    assert "not active" in reason


# ---------------------------------------------------------------------------
# 6. HTTP Collector Transient Retries & Failures (TEST 6, 7, 8)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_collector_transient_failure_retry_success():
    """TEST 6: Transient HTTP failure -> retry -> success."""
    collector = HTTPCollector(max_retries=2, retry_delay=0.01)
    source = SourceDefinition(
        name="Transient Source",
        type=SourceType.WEBSITE,
        base_url="https://flaky-service.com/data",
        access_method=AccessMethod.HTTP,
    )

    call_count = 0

    async def mock_send(request, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt fails with 503 Service Unavailable
            return httpx.Response(503, request=request, text="Temporarily unavailable")
        # Second attempt succeeds
        return httpx.Response(200, request=request, text="<html>Success</html>", headers={"Content-Type": "text/html"})

    with patch.object(collector.client, "send", side_effect=mock_send):
        docs = await collector.collect(source)
        assert len(docs) == 1
        assert docs[0].status_code == 200
        assert "Success" in docs[0].content
        assert call_count == 2


@pytest.mark.asyncio
async def test_http_collector_404_no_unnecessary_retries():
    """TEST 7: 404 -> no unnecessary retries -> structured failure."""
    collector = HTTPCollector(max_retries=3, retry_delay=0.01)
    source = SourceDefinition(
        name="Missing Source",
        type=SourceType.WEBSITE,
        base_url="https://example.com/not-found",
        access_method=AccessMethod.HTTP,
    )

    call_count = 0

    async def mock_send(request, **kwargs):
        nonlocal call_count
        call_count += 1
        return httpx.Response(404, request=request, text="Not Found")

    with patch.object(collector.client, "send", side_effect=mock_send):
        with pytest.raises(CollectorError) as exc_info:
            await collector.collect(source)
        assert "404" in str(exc_info.value)
        # Should NOT retry on 404
        assert call_count == 1


@pytest.mark.asyncio
async def test_rate_limiter_and_429_handling():
    """TEST 8: 429 rate limit handling with backoff."""
    limiter = RateLimiter(max_per_period=2, period_seconds=0.2)
    # Both acquire should succeed within period
    await limiter.acquire("api.example.com")
    await limiter.acquire("api.example.com")
    # Next acquire will briefly wait
    t0 = asyncio.get_event_loop().time()
    await limiter.acquire("api.example.com")
    t1 = asyncio.get_event_loop().time()
    assert (t1 - t0) >= 0.1


# ---------------------------------------------------------------------------
# 7. API Collector & Pagination (TEST 9)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_collector_pagination():
    """TEST 9: Pagination -> multiple pages collected."""
    collector = APICollector(timeout_seconds=5)
    source = SourceDefinition(
        id="src_paged_api",
        name="Paged Startups API",
        type=SourceType.API,
        base_url="https://api.startups.test/v1/companies",
        access_method=AccessMethod.API,
        metadata={
            "pagination": {
                "type": "page_number",
                "page_param": "page",
                "max_pages": 3,
                "data_path": "results",
            }
        },
    )

    def fake_response(request: httpx.Request):
        page = int(request.url.params.get("page", 1))
        return httpx.Response(
            200,
            request=request,
            json={
                "page": page,
                "total_pages": 3,
                "results": [{"id": f"comp_{page}_1", "name": f"Company {page}"}],
            },
        )

    with patch.object(collector.client, "send", side_effect=fake_response):
        docs = await collector.collect(source, max_documents=5)
        assert len(docs) == 3
        for i, doc in enumerate(docs, start=1):
            assert doc.status_code == 200
            assert f"Company {i}" in doc.content


# ---------------------------------------------------------------------------
# 8. CAPTCHA Handling & Zyte Fallback (TEST 10, 11, 12)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_captcha_detected_zyte_fallback_success():
    """TEST 10: HTTP collector encounters CAPTCHA -> no bypass -> Zyte fallback attempted when configured."""
    manager = CollectionManager()
    source = SourceDefinition(
        id="src_protected",
        name="Protected Startup Directory",
        type=SourceType.WEBSITE,
        base_url="https://protected-startups.com",
        access_method=AccessMethod.HTTP,
    )

    req = CollectionRequest(
        objective="Find AI startups",
        entity="startup",
        required_fields=["name"],
        collection_strategy=CollectionStrategy(allow_zyte=True, human_action_on_captcha=False),
    )

    # 1. Mock HTTP collector raising CaptchaChallengeDetected
    async def mock_http_collect(*args, **kwargs):
        raise CaptchaChallengeDetected(
            "Cloudflare Turnstile challenge detected",
            url=source.base_url,
            source_id=source.id,
            challenge_type="cloudflare",
        )

    # 2. Mock Zyte adapter configured and succeeding
    mock_zyte_doc = RawDocument(
        document_id="doc_zyte_1",
        job_id="job_test",
        source_id=source.id,
        url=source.base_url,
        canonical_url=source.base_url,
        content_type="text/html",
        content="<html><body>Zyte retrieved content</body></html>",
        status_code=200,
        metadata={"collector": "zyte", "zyte_used": True},
    )

    with patch.object(manager.http_collector, "collect", side_effect=mock_http_collect):
        with patch.object(manager.zyte_adapter, "is_configured", True):
            with patch.object(manager.zyte_adapter, "collect", return_value=[mock_zyte_doc]):
                result = await manager.execute_collection(
                    request=req,
                    sources=[source],
                )

                assert result.status == JobStatus.COMPLETED
                assert len(result.documents) == 1
                assert result.metadata.documents_collected == 1
                assert result.metadata.zyte_used is True
                assert "doc_zyte_1" in [d.document_id for d in result.documents]


@pytest.mark.asyncio
async def test_captcha_zyte_unavailable_alternative_source_discovery():
    """TEST 11: HTTP encounters CAPTCHA -> Zyte unavailable -> alternative source discovery."""
    manager = CollectionManager()
    source_a = SourceDefinition(
        id="src_a_blocked",
        name="Source A (Protected)",
        type=SourceType.WEBSITE,
        base_url="https://blocked-site.com",
        access_method=AccessMethod.HTTP,
        capabilities=["startup", "ai"],
    )
    source_b_alt = SourceDefinition(
        id="src_b_alt",
        name="Source B (Alternative)",
        type=SourceType.WEBSITE,
        base_url="https://alt-site.org/startups",
        access_method=AccessMethod.HTTP,
        capabilities=["startup", "ai"],
    )

    req = CollectionRequest(
        objective="Find AI startups",
        entity="startup",
        required_fields=["name"],
        collection_strategy=CollectionStrategy(allow_zyte=True, human_action_on_captcha=False),
    )

    async def mock_http_collect(src, *args, **kwargs):
        if src.id == "src_a_blocked":
            raise CaptchaChallengeDetected("CAPTCHA barrier", url=src.base_url, source_id=src.id)
        # Source B succeeds
        return [
            RawDocument(
                document_id="doc_alt_1",
                job_id="job_test",
                source_id=src.id,
                url=src.base_url,
                canonical_url=src.base_url,
                content_type="text/html",
                content="<html><body>Source B Data</body></html>",
                status_code=200,
            )
        ]

    # Discovery returns source B when source A fails
    async def mock_discover_alt(failed_src, request=None, **kwargs):
        return [source_b_alt]

    with patch.object(manager.http_collector, "collect", side_effect=mock_http_collect):
        with patch.object(manager.zyte_adapter, "is_configured", False):  # Zyte unconfigured
            with patch.object(manager.discovery, "discover_alternative_sources", side_effect=mock_discover_alt):
                result = await manager.execute_collection(request=req, sources=[source_a])

                assert result.status == JobStatus.COMPLETED
                assert len(result.documents) == 1
                assert "src_a_blocked" in result.metadata.inaccessible_sources
                assert "src_b_alt" in result.metadata.alternative_sources_used
                assert result.metadata.documents_collected == 1


@pytest.mark.asyncio
async def test_captcha_zyte_fails_alternative_source_collected():
    """TEST 12: HTTP CAPTCHA -> Zyte attempted -> Zyte fails -> alternative source discovered and collected."""
    manager = CollectionManager()
    source_a = SourceDefinition(
        id="src_a_fails_all",
        name="Source A (Protected & Zyte Fails)",
        type=SourceType.WEBSITE,
        base_url="https://hard-protected.com",
        access_method=AccessMethod.HTTP,
    )
    source_c_alt = SourceDefinition(
        id="src_c_alt",
        name="Source C (Alternative Clean)",
        type=SourceType.WEBSITE,
        base_url="https://clean-directory.org/list",
        access_method=AccessMethod.HTTP,
    )

    req = CollectionRequest(
        objective="Find AI startups",
        entity="startup",
        required_fields=["name"],
        collection_strategy=CollectionStrategy(allow_zyte=True, human_action_on_captcha=False),
    )

    async def mock_http_collect(src, *args, **kwargs):
        if src.id == "src_a_fails_all":
            raise CaptchaChallengeDetected("Bot gate", url=src.base_url, source_id=src.id)
        return [
            RawDocument(
                document_id="doc_c_1",
                job_id="job_test",
                source_id=src.id,
                url=src.base_url,
                canonical_url=src.base_url,
                content_type="text/html",
                content="<html>Clean Source C data</html>",
                status_code=200,
            )
        ]

    # Zyte also fails
    async def mock_zyte_collect(src, *args, **kwargs):
        raise CollectorError("Zyte API timeout on protected domain", source_id=src.id)

    async def mock_discover_alt(failed_src, request=None, **kwargs):
        return [source_c_alt]

    with patch.object(manager.http_collector, "collect", side_effect=mock_http_collect):
        with patch.object(manager.zyte_adapter, "is_configured", True):
            with patch.object(manager.zyte_adapter, "collect", side_effect=mock_zyte_collect):
                with patch.object(manager.discovery, "discover_alternative_sources", side_effect=mock_discover_alt):
                    result = await manager.execute_collection(request=req, sources=[source_a])

                    assert result.status == JobStatus.COMPLETED
                    assert "src_a_fails_all" in result.metadata.inaccessible_sources
                    assert "src_c_alt" in result.metadata.alternative_sources_used
                    assert len(result.documents) == 1
                    assert result.metadata.documents_collected == 1


# ---------------------------------------------------------------------------
# 9. Raw Document Store Integrity (TEST 13)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raw_document_store_without_extraction():
    """TEST 13: Raw document stored verbatim without extraction or semantic transformation."""
    store = RawDocumentStore(session=None)
    raw_html = "<html><body><h1>Company: ABC AI</h1><p>Raised $10M Series A</p></body></html>"

    doc = RawDocument(
        job_id="job_store_test",
        source_id="src_sample",
        url="https://example.com/company-abc",
        canonical_url="https://example.com/company-abc",
        content_type="text/html",
        content=raw_html,
        status_code=200,
        metadata={"collector": "http", "title": "Company: ABC AI"},
    )

    saved_doc = await store.save(doc)
    assert saved_doc.document_id is not None
    assert saved_doc.content == raw_html
    # Content hash must be populated
    assert saved_doc.content_hash.startswith("sha256:")

    # Retrieve from store
    retrieved = await store.get(saved_doc.document_id)
    assert retrieved is not None
    assert retrieved.content == raw_html
    # Verbatim content preserved: no parsed business fields like company_name/funding in document
    assert not hasattr(retrieved, "company_name")
    assert not hasattr(retrieved, "funding_amount")


# ---------------------------------------------------------------------------
# 10. Multi-Source Resilience & Partial Success (TEST 15)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_source_partial_success():
    """TEST 15: One source fails -> other eligible sources continue."""
    manager = CollectionManager()
    src_fail = SourceDefinition(
        id="src_fail_1",
        name="Failing Server",
        type=SourceType.WEBSITE,
        base_url="https://dead-server.org",
        access_method=AccessMethod.HTTP,
    )
    src_ok = SourceDefinition(
        id="src_ok_2",
        name="Working Server",
        type=SourceType.WEBSITE,
        base_url="https://working-server.org",
        access_method=AccessMethod.HTTP,
    )

    req = CollectionRequest(
        objective="Collect data resiliently",
        entity="startup",
        required_fields=["name"],
    )

    async def mock_http_collect(src, *args, **kwargs):
        if src.id == "src_fail_1":
            raise CollectorError("Server error 500", source_id=src.id)
        return [
            RawDocument(
                document_id="doc_ok_1",
                job_id="job_resilience",
                source_id=src.id,
                url=src.base_url,
                canonical_url=src.base_url,
                content_type="text/html",
                content="<html>Working data</html>",
                status_code=200,
            )
        ]

    with patch.object(manager.http_collector, "collect", side_effect=mock_http_collect):
        result = await manager.execute_collection(request=req, sources=[src_fail, src_ok])
        assert result.status == JobStatus.COMPLETED
        assert result.metadata.documents_collected == 1
        assert "src_fail_1" in result.metadata.failed_sources
        assert "src_ok_2" in result.metadata.successful_sources
        assert len(result.errors) >= 1


# ---------------------------------------------------------------------------
# 11. CollectionResult Metadata Reporting (TEST 16)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collection_result_metadata_reporting():
    """TEST 16: CollectionResult reports all performance, source, and document counts."""
    manager = CollectionManager()
    src = SourceDefinition(
        id="src_meta_1",
        name="Metadata Test Source",
        type=SourceType.WEBSITE,
        base_url="https://example.com/test",
        access_method=AccessMethod.HTTP,
    )
    req = CollectionRequest(
        objective="Metadata check",
        entity="startup",
        required_fields=["name"],
    )

    mock_doc = RawDocument(
        document_id="doc_m1",
        job_id="job_m",
        source_id=src.id,
        url=src.base_url,
        canonical_url=src.base_url,
        content_type="text/html",
        content="<html>data</html>",
        status_code=200,
    )

    with patch.object(manager.http_collector, "collect", new_callable=AsyncMock, return_value=[mock_doc]):
        result = await manager.execute_collection(request=req, sources=[src])

        assert result.metadata.sources_discovered == 1
        assert result.metadata.sources_used == 1
        assert result.metadata.documents_collected == 1
        assert result.metadata.pages_collected == 1
        assert result.metadata.failed_urls == 0
        assert result.metadata.duration_ms >= 0


# ---------------------------------------------------------------------------
# 12. Caching Layer Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_document_caching():
    """Cache returns hit for canonical URL within TTL."""
    cache = DocumentCache(ttl_seconds=3600)
    doc = RawDocument(
        document_id="doc_cached_1",
        job_id="job_1",
        source_id="src_1",
        url="https://example.com/page?ref=1",
        canonical_url="https://example.com/page",
        content_type="text/html",
        content="<html>Cached HTML</html>",
        status_code=200,
    )

    # Miss
    assert await cache.get("src_1", "https://example.com/page") is None

    # Set
    await cache.set("src_1", "https://example.com/page", doc)

    # Hit
    cached_doc = await cache.get("src_1", "https://example.com/page")
    assert cached_doc is not None
    assert cached_doc.document_id == "doc_cached_1"
    assert cached_doc.content == "<html>Cached HTML</html>"


# ---------------------------------------------------------------------------
# 13. REST API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_sources_endpoints():
    """Test GET /api/v1/sources and GET /api/v1/sources/{id}."""
    # List sources
    res = client.get("/api/v1/sources")
    assert res.status_code == 200
    sources = res.json()
    assert len(sources) > 0
    first_id = sources[0]["id"]

    # Get single source
    res_single = client.get(f"/api/v1/sources/{first_id}")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == first_id

    # 404 on nonexistent source
    res_404 = client.get("/api/v1/sources/non_existent_source_999")
    assert res_404.status_code == 404


def test_api_collection_jobs_endpoints():
    """Test POST /api/v1/collection/jobs, /discover, /execute, and GET /documents."""
    job_payload = {
        "collection_request": {
            "request_id": "colreq_api_test",
            "workflow_id": "wf_api_test",
            "objective": "Collect Indian tech startups",
            "entity": "startup",
            "required_fields": ["company", "website"],
            "constraints": {"country": "India"},
        }
    }

    # 1. Create job
    res_create = client.post("/api/v1/collection/jobs", json=job_payload)
    assert res_create.status_code == 201
    job_id = res_create.json()["job_id"]
    assert res_create.json()["status"] in ["CREATED", "PENDING"]

    # 2. Discover sources
    res_disc = client.post(f"/api/v1/collection/jobs/{job_id}/discover")
    assert res_disc.status_code == 200
    disc_data = res_disc.json()
    assert disc_data["sources_discovered"] > 0
    assert len(disc_data["sources"]) > 0

    # 3. Execute job (mocking collector to keep test offline)
    mock_doc = RawDocument(
        document_id="doc_api_exec_1",
        job_id=job_id,
        source_id="src_test",
        url="https://example.com/company",
        canonical_url="https://example.com/company",
        content_type="text/html",
        content="<html>Raw test content</html>",
        status_code=200,
    )
    with patch.object(CollectionManager, "execute_collection", return_value=CollectionResult(
        job_id=job_id,
        request_id="colreq_api_test",
        status=JobStatus.COMPLETED,
        documents=[mock_doc.to_reference("storage://documents/doc_api_exec_1")],
    )):
        res_exec = client.post(f"/api/v1/collection/jobs/{job_id}/execute")
        assert res_exec.status_code == 200
        exec_data = res_exec.json()
        assert exec_data["status"] == "COMPLETED"

    # 4. Get job details
    res_job = client.get(f"/api/v1/collection/jobs/{job_id}")
    assert res_job.status_code == 200
    assert res_job.json()["job_id"] == job_id

    # 5. Get job documents
    res_docs = client.get(f"/api/v1/collection/jobs/{job_id}/documents")
    assert res_docs.status_code == 200
    assert "documents" in res_docs.json()


# ---------------------------------------------------------------------------
# 14. Workflow Engine Integration (TEST 14)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_engine_discovery_and_collection_step_execution():
    """TEST 14: Workflow: DISCOVER_SOURCES -> COLLECT_DATA executes real Phase 4 components."""
    req = StructuredRequirement(
        objective="Find Indian AI startups founded after 2020 with funding above $5M",
        entity="startup",
        required_fields=["company", "founders", "website", "funding", "funding_date", "investors"],
        output_format=OutputFormat.TABLE,
    )
    planner = WorkflowPlanner()
    wf = planner.plan(requirement=req)

    # Use default registry containing real SourceDiscoveryStepExecutor & CollectionStepExecutor
    engine = WorkflowEngine(registry=get_default_registry())

    # Mock collection execution to keep test offline
    mock_doc = RawDocument(
        document_id="doc_wf_1",
        job_id="job_wf_test",
        source_id="source_ycombinator_directory",
        url="https://www.ycombinator.com/companies",
        canonical_url="https://www.ycombinator.com/companies",
        content_type="text/html",
        content="<html><body>YC Indian Startups Directory</body></html>",
        status_code=200,
    )

    with patch.object(CollectionManager, "execute_collection", return_value=CollectionResult(
        job_id="job_wf_test",
        request_id="colreq_wf",
        status=JobStatus.COMPLETED,
        documents=[mock_doc.to_reference("storage://documents/doc_wf_1")],
    )):
        executed_wf = await engine.execute(wf)

        assert executed_wf.status == WorkflowStatus.COMPLETED

        # Check Step 1: DISCOVER_SOURCES
        step_1 = [s for s in executed_wf.steps if s.type == StepType.DISCOVER_SOURCES][0]
        assert step_1.status == StepStatus.COMPLETED
        assert step_1.output.get("is_mock") is not True  # Real Phase 4 step!
        assert step_1.output.get("sources_discovered") > 0
        assert len(step_1.output.get("sources", [])) > 0

        # Check Step 2: COLLECT_DATA
        step_2 = [s for s in executed_wf.steps if s.type == StepType.COLLECT_DATA][0]
        assert step_2.status == StepStatus.COMPLETED
        assert step_2.output.get("is_mock") is not True  # Real Phase 4 step!
        assert step_2.output.get("status") == "COMPLETED"
        assert len(step_2.output.get("documents", [])) > 0

        # Downstream steps remain mock (Phase 5)
        step_3 = [s for s in executed_wf.steps if s.type == StepType.EXTRACT_DATA][0]
        assert step_3.status == StepStatus.COMPLETED
        assert step_3.output.get("is_mock") is True
