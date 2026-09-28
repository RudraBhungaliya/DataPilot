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
from app.ai.schemas import StructuredRequirement


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


# ---------------------------------------------------------------------------
# 7. Workflow human-in-the-loop pause & resume
# ---------------------------------------------------------------------------

def _flaky_registry():
    """Registry whose COLLECT_DATA pauses for human action once, then succeeds."""
    from app.workflows.registry import get_mock_registry
    from app.workflows.types import StepType
    from app.workflows.executors.base import BaseStepExecutor, StepResult

    state = {"calls": 0}

    class FlakyCollector(BaseStepExecutor):
        async def execute(self, step, context):
            state["calls"] += 1
            if state["calls"] == 1:
                return StepResult(
                    success=False,
                    error="CAPTCHA encountered",
                    metadata={"human_action_required": True, "job_id": "job_paused_1"},
                )
            return StepResult(success=True, output={"is_mock": False}, metadata={"job_id": "job_paused_1"})

    registry = get_mock_registry()
    registry.register(StepType.COLLECT_DATA, FlakyCollector())
    return registry, state


@pytest.mark.asyncio
async def test_engine_pause_leaves_downstream_pending_then_resumes():
    from app.workflows.engine import WorkflowEngine
    from app.workflows.planner import WorkflowPlanner
    from app.workflows.types import StepType, StepStatus, WorkflowStatus

    registry, state = _flaky_registry()
    req = StructuredRequirement(objective="x", entity="startup", required_fields=["name"])
    wf = WorkflowPlanner().plan(requirement=req)
    engine = WorkflowEngine(registry=registry)

    wf = await engine.execute(wf)
    assert wf.status == WorkflowStatus.PAUSED
    collect_step = [s for s in wf.steps if s.type == StepType.COLLECT_DATA][0]
    extract_step = [s for s in wf.steps if s.type == StepType.EXTRACT_DATA][0]
    assert collect_step.status == StepStatus.HUMAN_ACTION_REQUIRED
    # Downstream must remain PENDING (resumable), not SKIPPED
    assert extract_step.status == StepStatus.PENDING

    # Resume by resetting the paused step and re-running the engine
    collect_step.status = StepStatus.PENDING
    wf = await engine.execute(wf)
    assert wf.status == WorkflowStatus.COMPLETED
    assert state["calls"] == 2
    assert all(s.status == StepStatus.COMPLETED for s in wf.steps)


def test_api_resume_requires_paused_state():
    """Resuming a workflow that is not paused returns 409; unknown id returns 404."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    plan = client.post(
        "/api/v1/workflows/plan",
        json={
            "requirement": {
                "objective": "Find AI startups",
                "entity": "startup",
                "required_fields": ["company_name"],
                "output_format": "table",
            }
        },
    )
    assert plan.status_code == 200
    workflow_id = plan.json()["workflow"]["workflow_id"]

    resume_res = client.post(f"/api/v1/workflows/{workflow_id}/resume")
    assert resume_res.status_code == 409

    missing_res = client.post("/api/v1/workflows/does-not-exist/resume")
    assert missing_res.status_code == 404


def test_api_workflow_execute_pause_then_resume():
    """Full API round-trip: execute -> PAUSED -> resume -> COMPLETED."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.v1.endpoints.workflows import workflow_service
    from app.workflows.engine import WorkflowEngine

    client = TestClient(app)
    registry, _ = _flaky_registry()

    with patch.object(workflow_service, "engine", WorkflowEngine(registry=registry)):
        plan = client.post(
            "/api/v1/workflows/plan",
            json={
                "requirement": {
                    "objective": "Find AI startups",
                    "entity": "startup",
                    "required_fields": ["company_name"],
                    "output_format": "table",
                }
            },
        )
        workflow_id = plan.json()["workflow"]["workflow_id"]

        exec_res = client.post(f"/api/v1/workflows/{workflow_id}/execute")
        assert exec_res.status_code == 200
        assert exec_res.json()["workflow"]["status"] == "PAUSED"

        # Re-executing a paused workflow is rejected to prevent duplicate runs
        conflict = client.post(f"/api/v1/workflows/{workflow_id}/execute")
        assert conflict.status_code == 409

        resume_res = client.post(f"/api/v1/workflows/{workflow_id}/resume")
        assert resume_res.status_code == 200
        assert resume_res.json()["workflow"]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_collection_executor_resumes_existing_job():
    """COLLECT_DATA resumes the paused collection job instead of creating a new one."""
    from app.workflows.executors.collection import CollectionStepExecutor
    from app.workflows.schemas import WorkflowStep
    from app.workflows.executors.base import ExecutionContext
    from app.workflows.types import StepType
    from app.collection.schemas import CollectionResult

    class FakeJob:
        status = JobStatus.HUMAN_ACTION_REQUIRED.value

    class FakeService:
        def __init__(self):
            self.resumed = []
            self.created = 0

        async def get_job(self, job_id):
            return FakeJob()

        async def resume_job(self, job_id):
            self.resumed.append(job_id)
            return CollectionResult(
                job_id=job_id, request_id="r", status=JobStatus.COMPLETED.value, documents=[]
            )

        async def create_job(self, request):
            self.created += 1
            raise AssertionError("create_job must not be called on resume")

    service = FakeService()
    executor = CollectionStepExecutor(service=service)
    step = WorkflowStep(
        id="step_2",
        name="Collect",
        type=StepType.COLLECT_DATA,
        description="d",
        order=2,
        depends_on=[],
        config={},
        metadata={"job_id": "job_paused", "human_action_required": True},
    )
    req = StructuredRequirement(objective="x", entity="startup", required_fields=["name"])
    context = ExecutionContext(workflow_id="wf", input_requirement=req)

    result = await executor.execute(step=step, context=context)
    assert result.success is True
    assert service.resumed == ["job_paused"]
    assert service.created == 0
    assert step.metadata["human_action_required"] is False


# ---------------------------------------------------------------------------
# 8. Collection list endpoints used by the UI
# ---------------------------------------------------------------------------

def test_api_collection_list_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    created = client.post(
        "/api/v1/collection/jobs",
        json={"collection_request": {"objective": "List me", "entity": "startup"}},
    )
    assert created.status_code == 201

    jobs = client.get("/api/v1/collection/jobs")
    assert jobs.status_code == 200
    assert isinstance(jobs.json(), list) and len(jobs.json()) >= 1

    docs = client.get("/api/v1/collection/documents")
    assert docs.status_code == 200
    assert isinstance(docs.json(), list)


