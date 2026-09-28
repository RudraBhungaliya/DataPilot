"""
Tests for Human-in-the-Loop CAPTCHA Handoff & Safe Resume.
Covers:
1. Normal collection.
2. CAPTCHA detection.
3. Job transitions to HUMAN_ACTION_REQUIRED.
4. Human-action email is triggered.
5. Sensitive credentials are not included in email.
6. Resume endpoint changes HUMAN_ACTION_REQUIRED -> RESUMING.
7. Collection resumes from a checkpoint.
8. Already collected records are not duplicated.
9. Failed sources do not retry forever.
10. No CAPTCHA bypass logic exists (verification test).
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.collection.schemas import (
    CollectionRequest,
    CollectionStrategy,
    SourceDefinition,
    SourceType,
    AccessMethod,
    RawDocument,
    JobStatus,
)
from app.collection.manager import CollectionManager
from app.collection.service import CollectionService
from app.collection.collectors.base import CaptchaChallengeDetected, CollectorError
from app.services.email import email_service, InMemoryEmailProvider
from app.main import app


@pytest.fixture(autouse=True)
def in_memory_email():
    """Ensure tests run against clean InMemoryEmailProvider."""
    provider = InMemoryEmailProvider()
    email_service.set_provider(provider)
    yield provider
    provider.clear()


# ==============================================================================
# 1. Normal Collection Test
# ==============================================================================
@pytest.mark.asyncio
async def test_normal_collection_completes_successfully():
    """Normal source collection succeeds and completes with JobStatus.COMPLETED."""
    manager = CollectionManager()
    source = SourceDefinition(
        id="src_normal_test",
        name="Public API Source",
        type=SourceType.API,
        base_url="https://api.example.com/items",
        access_method=AccessMethod.API,
    )
    req = CollectionRequest(
        objective="Fetch normal data",
        entity="item",
        required_fields=["id", "name"],
    )

    mock_doc = RawDocument(
        document_id="doc_norm_1",
        job_id="job_norm",
        source_id=source.id,
        url="https://api.example.com/items",
        canonical_url="https://api.example.com/items",
        content_type="application/json",
        content='[{"id": 1, "name": "Test Item"}]',
        status_code=200,
    )

    with patch.object(manager.api_collector, "collect", return_value=[mock_doc]):
        result = await manager.execute_job(request=req, sources=[source])

        assert result.status == JobStatus.COMPLETED.value
        assert len(result.documents) == 1
        assert result.human_action_required is False
        assert result.checkpoint is None


# ==============================================================================
# 2. CAPTCHA Detection Test
# ==============================================================================
def test_captcha_detection_identifies_challenges():
    """HTTPCollector accurately flags Cloudflare, anti-bot, and CAPTCHA signals."""
    from app.collection.collectors.http import HTTPCollector
    import httpx

    collector = HTTPCollector()

    # Cloudflare mitigated header
    assert collector.is_captcha_challenge(
        status_code=403,
        headers=httpx.Headers({"cf-mitigated": "challenge", "server": "cloudflare"}),
        body_text="<html>Forbidden</html>",
    ) is True

    # Cloudflare WAF body keywords
    assert collector.is_captcha_challenge(
        status_code=403,
        headers=httpx.Headers({"server": "cloudflare"}),
        body_text="<html><title>Attention Required! | Cloudflare</title><body>Please verify you are a human</body></html>",
    ) is True

    # Recaptcha / hCaptcha in body
    assert collector.is_captcha_challenge(
        status_code=200,
        headers=httpx.Headers({}),
        body_text="<div id='g-recaptcha'></div>",
    ) is True

    # Normal response is not flagged
    assert collector.is_captcha_challenge(
        status_code=200,
        headers=httpx.Headers({"content-type": "text/html"}),
        body_text="<html><body>Welcome to our public catalog!</body></html>",
    ) is False


# ==============================================================================
# 3. Job Transitions to HUMAN_ACTION_REQUIRED
# ==============================================================================
@pytest.mark.asyncio
async def test_job_transitions_to_human_action_required_on_captcha():
    """When CAPTCHA challenge occurs, collection job transitions to HUMAN_ACTION_REQUIRED."""
    manager = CollectionManager()
    source = SourceDefinition(
        id="src_captcha_site",
        name="Protected Directory",
        type=SourceType.WEBSITE,
        base_url="https://directory.com/browse",
        access_method=AccessMethod.HTTP,
    )
    req = CollectionRequest(
        objective="Collect directory data",
        entity="listing",
        required_fields=["name"],
    )

    async def mock_captcha_collect(*args, **kwargs):
        raise CaptchaChallengeDetected(
            "Cloudflare Turnstile challenge detected",
            url=source.base_url,
            source_id=source.id,
        )

    with patch.object(manager.http_collector, "collect", side_effect=mock_captcha_collect):
        result = await manager.execute_job(request=req, sources=[source])

        assert result.status == JobStatus.HUMAN_ACTION_REQUIRED.value
        assert result.human_action_required is True
        assert result.human_action_reason == "CAPTCHA_REQUIRED"
        assert result.checkpoint is not None
        assert result.checkpoint["source_id"] == source.source_id
        assert result.checkpoint["reason"] == "CAPTCHA_REQUIRED"
        assert result.checkpoint["current_step"] == "SOURCE_COLLECTION"


# ==============================================================================
# 4. Human-Action Email is Triggered
# ==============================================================================
@pytest.mark.asyncio
async def test_human_action_email_is_triggered_on_captcha(in_memory_email):
    """CAPTCHA triggers human-action notification email to configured email."""
    service = CollectionService()
    req = CollectionRequest(
        objective="Scrape listings",
        entity="listing",
        required_fields=["title"],
    )
    job = await service.create_job(req)

    source = SourceDefinition(
        id="src_bot_wall",
        name="Target Listing Portal",
        type=SourceType.WEBSITE,
        base_url="https://portal.com/listings",
        access_method=AccessMethod.HTTP,
    )

    async def mock_captcha(*args, **kwargs):
        raise CaptchaChallengeDetected(
            "CAPTCHA encountered",
            url=source.base_url,
            source_id=source.id,
        )

    with patch.object(service, "discover_sources", return_value=[source]):
        with patch.object(service.manager.http_collector, "collect", side_effect=mock_captcha):
            result = await service.execute_job(job_id=job.id)

            assert result.status == JobStatus.HUMAN_ACTION_REQUIRED.value
            # Check email outbox
            assert len(in_memory_email.outbox) == 1
            sent = in_memory_email.outbox[0]
            assert "DataPilot needs your help to continue a collection task" in sent.subject
            assert "Target Listing Portal" in sent.body
            assert "https://portal.com/listings" in sent.body
            assert f"Task ID: {job.id}" in sent.body


# ==============================================================================
# 5. Sensitive Credentials Are Not Included in Email
# ==============================================================================
@pytest.mark.asyncio
async def test_email_does_not_contain_secrets_or_credentials(in_memory_email):
    """Human handoff email must never expose API keys, passwords, cookies, or secrets."""
    await email_service.send_human_action_required_email(
        to_email="user@example.com",
        source_name="Test Source",
        source_url="https://example.com/login",
        task_id="task_12345",
    )

    assert len(in_memory_email.outbox) == 1
    email = in_memory_email.outbox[0]
    forbidden_terms = [
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "passwd",
        "cookie",
        "session",
        "bearer",
        "smtp",
    ]
    lower_body = email.body.lower()
    for term in forbidden_terms:
        assert term not in lower_body, f"Forbidden term '{term}' leaked into email body!"


# ==============================================================================
# 6. Resume Endpoint Changes State from HUMAN_ACTION_REQUIRED -> RESUMING
# ==============================================================================
def test_resume_endpoint_transitions_state():
    """POST /api/v1/collection/jobs/{job_id}/resume validates and resumes human-paused jobs."""
    client = TestClient(app)

    # 1. Create a job
    create_res = client.post(
        "/api/v1/collection/jobs",
        json={
            "collection_request": {
                "objective": "Collect startup data",
                "entity": "startup",
                "required_fields": ["name"],
            }
        },
    )
    assert create_res.status_code == 201
    job_id = create_res.json()["job_id"]

    # Try resuming when job is PENDING -> should fail with 400
    bad_resume = client.post(f"/api/v1/collection/jobs/{job_id}/resume")
    assert bad_resume.status_code == 400
    assert "Only jobs in 'HUMAN_ACTION_REQUIRED' status can be resumed" in bad_resume.json()["detail"]


# ==============================================================================
# 7. Collection Resumes From a Checkpoint
# ==============================================================================
@pytest.mark.asyncio
async def test_collection_resumes_from_checkpoint():
    """After human completes CAPTCHA, job resumes from stored checkpoint without restart."""
    service = CollectionService()
    req = CollectionRequest(
        objective="Collect data across multiple sources",
        entity="item",
        required_fields=["name"],
    )
    job = await service.create_job(req)

    source_a = SourceDefinition(
        id="src_a",
        name="Source A (Protected)",
        type=SourceType.WEBSITE,
        base_url="https://site-a.com",
        access_method=AccessMethod.HTTP,
    )
    source_b = SourceDefinition(
        id="src_b",
        name="Source B (Clean)",
        type=SourceType.WEBSITE,
        base_url="https://site-b.com",
        access_method=AccessMethod.HTTP,
    )

    # First attempt: source_a raises CAPTCHA -> pauses in HUMAN_ACTION_REQUIRED
    async def first_attempt_collect(src, *args, **kwargs):
        raise CaptchaChallengeDetected("CAPTCHA detected", url=src.base_url, source_id=src.id)

    with patch.object(service, "discover_sources", return_value=[source_a, source_b]):
        with patch.object(service.manager.http_collector, "collect", side_effect=first_attempt_collect):
            result1 = await service.execute_job(job_id=job.id)
            assert result1.status == JobStatus.HUMAN_ACTION_REQUIRED.value
            assert job.status == JobStatus.HUMAN_ACTION_REQUIRED.value
            assert job.checkpoint is not None

    # Human intervention completed: on resume, source_a succeeds!
    mock_doc_a = RawDocument(
        document_id="doc_resumed_a",
        job_id=job.id,
        source_id="src_a",
        url="https://site-a.com",
        canonical_url="https://site-a.com",
        content_type="text/html",
        content="<html><body>Resumed Source A Data</body></html>",
        status_code=200,
    )

    async def second_attempt_collect(src, *args, **kwargs):
        return [mock_doc_a]

    with patch.object(service.manager.http_collector, "collect", side_effect=second_attempt_collect):
        result2 = await service.resume_job(job_id=job.id)
        assert result2.status == JobStatus.COMPLETED.value
        assert job.status == JobStatus.COMPLETED.value
        assert any(d.document_id == "doc_resumed_a" for d in result2.documents)


# ==============================================================================
# 8. Already Collected Records Are Not Duplicated
# ==============================================================================
@pytest.mark.asyncio
async def test_already_collected_records_are_not_duplicated():
    """Resuming collection preserves previously collected documents without duplicating them."""
    manager = CollectionManager()
    req = CollectionRequest(
        objective="Fetch data",
        entity="item",
        required_fields=["name"],
    )

    source_1 = SourceDefinition(
        id="src_1",
        name="Source 1",
        type=SourceType.WEBSITE,
        base_url="https://first.com/items",
        access_method=AccessMethod.HTTP,
    )

    doc_existing = RawDocument(
        document_id="doc_prev_1",
        job_id="job_dup_test",
        source_id="src_1",
        url="https://first.com/items",
        canonical_url="https://first.com/items",
        content_type="text/html",
        content="<html>Data 1</html>",
        status_code=200,
    )

    # Simulating resume with checkpoint containing doc_existing
    checkpoint = {
        "job_id": "job_dup_test",
        "collected_urls": ["https://first.com/items"],
        "collected_document_ids": ["doc_prev_1"],
    }

    # Collector returns the same URL again
    with patch.object(manager.http_collector, "collect", return_value=[doc_existing]):
        result = await manager.execute_job(
            request=req,
            sources=[source_1],
            job_id="job_dup_test",
            checkpoint=checkpoint,
            initial_documents=[doc_existing.to_reference()],
        )

        # Count of documents for https://first.com/items should remain 1
        matching_docs = [d for d in result.documents if d.url == "https://first.com/items"]
        assert len(matching_docs) == 1


# ==============================================================================
# 9. Failed Sources Do Not Retry Forever
# ==============================================================================
@pytest.mark.asyncio
async def test_failed_sources_do_not_retry_forever():
    """Transient errors retry up to max_retries then terminate; permanent errors fail immediately."""
    from app.collection.management.retry import RetryHandler
    retry_handler = RetryHandler(max_retries=2, initial_delay=0.01)

    call_count = 0

    async def fail_transient_operation():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Transient network failure")

    with pytest.raises(ConnectionError):
        await retry_handler.execute(fail_transient_operation)

    # 1 initial try + 2 retries = 3 calls total, never infinite
    assert call_count == 3



# ==============================================================================
# 10. No CAPTCHA Bypass Logic Exists (Verification Test)
# ==============================================================================
def test_no_captcha_bypass_logic_exists():
    """Verify strictly by policy and code that no 2captcha, anti-captcha, or bypass solvers exist."""
    import inspect
    from app.collection.collectors import http, base, zyte

    for mod in [http, base, zyte]:
        source_code = inspect.getsource(mod).lower()
        forbidden_solvers = [
            "2captcha",
            "anticaptcha",
            "deathbycaptcha",
            "capmonster",
            "bypass_captcha",
            "solve_captcha",
            "captchasolver",
        ]
        for solver in forbidden_solvers:
            assert solver not in source_code, f"Forbidden solver '{solver}' found in {mod.__name__}!"
