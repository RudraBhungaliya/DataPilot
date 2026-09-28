"""
Phase 7 tests: authentication, rate limiting, metrics, background jobs.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.main import app
from app.core.config import settings


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_endpoints_open_when_auth_disabled():
    client = TestClient(app)
    assert client.get("/api/v1/datasets").status_code == 200
    assert client.get("/api/v1/sources").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_auth_requires_key_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "BOOTSTRAP_API_KEY", "bootstrap-test-key")
    client = TestClient(app)

    # No key -> 401
    assert client.get("/api/v1/datasets").status_code == 401
    # Wrong key -> 401
    assert client.get("/api/v1/datasets", headers={"X-API-Key": "nope"}).status_code == 401
    # Bootstrap key -> allowed
    assert client.get("/api/v1/datasets", headers={"X-API-Key": "bootstrap-test-key"}).status_code == 200
    # Health stays public
    assert client.get("/api/v1/health").status_code == 200


def test_api_key_lifecycle(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "BOOTSTRAP_API_KEY", "bootstrap-test-key")
    client = TestClient(app)
    admin = {"X-API-Key": "bootstrap-test-key"}

    created = client.post("/api/v1/auth/keys", json={"name": "unit-test-key"}, headers=admin)
    assert created.status_code == 201
    body = created.json()
    raw_key = body["api_key"]
    key_id = body["id"]
    assert raw_key.startswith("dp_")
    assert body["key_prefix"] == raw_key[:10]

    # The generated key authenticates
    assert client.get("/api/v1/datasets", headers={"X-API-Key": raw_key}).status_code == 200

    # Listing never exposes the secret
    listing = client.get("/api/v1/auth/keys", headers=admin).json()
    assert any(k["id"] == key_id for k in listing)
    assert all("api_key" not in k for k in listing)

    # Revocation immediately blocks the key
    assert client.delete(f"/api/v1/auth/keys/{key_id}", headers=admin).status_code == 200
    assert client.get("/api/v1/datasets", headers={"X-API-Key": raw_key}).status_code == 401


def test_api_keys_are_stored_hashed(monkeypatch):
    from app.core.security import hash_api_key, generate_api_key

    raw = generate_api_key()
    digest = hash_api_key(raw)
    assert raw not in digest
    assert len(digest) == 64
    assert hash_api_key(raw) == digest  # deterministic


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limit_returns_429(monkeypatch):
    import uuid

    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    client = TestClient(app)
    bucket = {"X-API-Key": f"rl-test-{uuid.uuid4().hex}"}

    assert client.get("/api/v1/datasets", headers=bucket).status_code == 200
    assert client.get("/api/v1/datasets", headers=bucket).status_code == 200
    assert client.get("/api/v1/datasets", headers=bucket).status_code == 429


# ---------------------------------------------------------------------------
# Metrics + observability
# ---------------------------------------------------------------------------

def test_metrics_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "METRICS_ENABLED", True)
    client = TestClient(app)
    response = client.get("/api/v1/datasets")
    assert response.status_code == 200
    # Timing header is attached by the observability middleware
    assert "X-Process-Time-Ms" in response.headers

    body = client.get("/metrics").text
    assert "datapilot_requests_total" in body
    assert 'path="/api/v1/datasets"' in body


# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_background_job_lifecycle():
    from app.jobs.service import get_job_service, JobStatus
    from app.jobs.worker import get_worker

    service = get_job_service()
    worker = get_worker()

    async def echo_handler(payload):
        return {"echo": payload.get("x")}

    worker.register("test.echo", echo_handler)
    job = await service.submit("test.echo", {"x": 42})
    assert job.status == JobStatus.QUEUED.value

    await worker.process(job.id)
    done = await service.get(job.id)
    assert done.status == JobStatus.COMPLETED.value
    assert done.result == {"echo": 42}

    async def boom_handler(payload):
        raise RuntimeError("kaboom")

    worker.register("test.boom", boom_handler)
    failing = await service.submit("test.boom", {})
    await worker.process(failing.id)
    failed = await service.get(failing.id)
    assert failed.status == JobStatus.FAILED.value
    assert "kaboom" in (failed.error or "")


def test_execute_async_endpoint_queues_job():
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
    workflow_id = plan.json()["workflow"]["workflow_id"]

    submitted = client.post(f"/api/v1/workflows/{workflow_id}/execute-async")
    assert submitted.status_code == 202
    task_id = submitted.json()["id"]
    assert submitted.json()["kind"] == "workflow.execute"

    fetched = client.get(f"/api/v1/jobs/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] in ("QUEUED", "RUNNING", "COMPLETED", "FAILED")

    listing = client.get("/api/v1/jobs")
    assert listing.status_code == 200
    assert any(j["id"] == task_id for j in listing.json())

    assert client.get("/api/v1/jobs/stats").status_code == 200
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404


