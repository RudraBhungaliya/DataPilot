"""
Tests for the intelligence layer: dynamic planning, grounding/availability,
search discovery, and fuzzy deduplication.
"""

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ai.schemas import StructuredRequirement
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.discovery.grounding import availability_score, estimate_field_availability
from app.collection.discovery.search_provider import SearchDiscoveryProvider, SearchResult
from app.collection.schemas import (
    AccessMethod,
    CollectionRequest,
    SourceDefinition,
    SourceType,
)
from app.pipeline.schemas import ExtractionRecord
from app.pipeline.stages import mark_duplicates
from app.workflows.planner import WorkflowPlanner
from app.workflows.types import StepType


# ---------------------------------------------------------------------------
# Dynamic planning
# ---------------------------------------------------------------------------

def test_planner_is_request_adaptive():
    planner = WorkflowPlanner()

    # Simple request: no sparse fields, table output -> no ENRICH, no EXPORT
    simple = planner.plan(requirement=StructuredRequirement(
        objective="Find internships", entity="job_posting",
        required_fields=["company_name", "role"], output_format="table",
    ))
    simple_types = {s.type for s in simple.steps}
    assert StepType.ENRICH_DATA not in simple_types
    assert StepType.EXPORT_DATA not in simple_types
    assert len(simple.steps) == 7

    # Richer request: sparse field + CSV -> ENRICH and EXPORT are added
    rich = planner.plan(requirement=StructuredRequirement(
        objective="Find startups", entity="startup",
        required_fields=["company_name", "founded_year", "employee_count"],
        output_format="csv",
    ))
    rich_types = {s.type for s in rich.steps}
    assert StepType.ENRICH_DATA in rich_types
    assert StepType.EXPORT_DATA in rich_types
    assert len(rich.steps) == 9
    assert "planning_notes" in rich.metadata


def test_planner_dedup_keys_are_entity_aware():
    planner = WorkflowPlanner()
    wf = planner.plan(requirement=StructuredRequirement(
        objective="jobs", entity="job_posting",
        required_fields=["company_name", "role", "application_url"], output_format="table",
    ))
    dedup = [s for s in wf.steps if s.type == StepType.DEDUPLICATE_DATA][0]
    assert dedup.config["deduplication_keys"] == ["application_url", "company_name", "role"]


# ---------------------------------------------------------------------------
# Fuzzy deduplication
# ---------------------------------------------------------------------------

def test_fuzzy_dedup_merges_near_duplicates():
    records = [
        ExtractionRecord(entity="company", data={"company_name": "Acme Inc"}),
        ExtractionRecord(entity="company", data={"company_name": "Acme Inc."}),   # near-duplicate
        ExtractionRecord(entity="company", data={"company_name": "Beta Corp"}),   # distinct
    ]
    removed = mark_duplicates(records, ["company_name"], match_threshold=0.9)
    assert removed == 1
    assert records[1].is_duplicate is True
    assert records[2].is_duplicate is False


def test_exact_dedup_when_threshold_is_one():
    records = [
        ExtractionRecord(entity="company", data={"company_name": "Acme Inc"}),
        ExtractionRecord(entity="company", data={"company_name": "Acme Inc."}),
    ]
    assert mark_duplicates(records, ["company_name"], match_threshold=1.0) == 0


# ---------------------------------------------------------------------------
# Grounding / availability
# ---------------------------------------------------------------------------

def test_field_availability_estimation():
    sources = [
        SourceDefinition(
            id="src_a", name="Startup Directory", base_url="https://startups.example",
            type=SourceType.WEBSITE, access_method=AccessMethod.HTTP,
            capabilities=["startup", "company", "funding", "investors"],
        ),
        SourceDefinition(
            id="src_b", name="Jobs Board", base_url="https://jobs.example",
            type=SourceType.WEBSITE, access_method=AccessMethod.HTTP,
            capabilities=["job_posting", "role", "salary"],
        ),
    ]
    estimates = {e["field"]: e["status"] for e in estimate_field_availability(
        ["company_name", "funding", "salary", "employee_count"], sources
    )}
    assert estimates["company_name"] == "obtainable"
    assert estimates["funding"] == "obtainable"
    assert estimates["salary"] == "obtainable"
    assert estimates["employee_count"] == "unknown"
    assert availability_score(["company_name", "funding"], sources) == 1.0


# ---------------------------------------------------------------------------
# Search-based discovery
# ---------------------------------------------------------------------------

class _MockSearchProvider:
    name = "mock"

    def __init__(self, results):
        self._results = results

    def is_configured(self):
        return True

    async def search(self, query, max_results):
        return self._results


@pytest.mark.asyncio
async def test_search_discovery_builds_sources_and_dedups_domains():
    provider = _MockSearchProvider([
        SearchResult(title="Startup List A", url="https://alpha.example/list", snippet="startups"),
        SearchResult(title="Startup List A mirror", url="https://www.alpha.example/other", snippet=""),
        SearchResult(title="Beta Directory", url="https://beta.example/directory", snippet=""),
    ])
    discovery = SearchDiscoveryProvider(search_provider=provider)
    request = CollectionRequest(
        objective="Find startups", entity="startup", required_fields=["company_name", "funding"],
    )
    sources = await discovery.discover(request)

    assert len(sources) == 2  # alpha.example deduped (www + non-www)
    domains = {s.domain for s in sources}
    assert domains == {"alpha.example", "beta.example"}
    assert all((s.metadata or {}).get("discovered_by") == "web_search" for s in sources)


@pytest.mark.asyncio
async def test_search_discovery_noop_without_provider():
    discovery = SearchDiscoveryProvider(search_provider=None)
    sources = await discovery.discover(CollectionRequest(objective="x", entity="startup"))
    assert sources == []


# ---------------------------------------------------------------------------
# Availability API
# ---------------------------------------------------------------------------

def test_availability_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    res = client.post("/api/v1/collection/availability", json={
        "entity": "startup",
        "required_fields": ["company_name", "funding", "founded_year"],
        "constraints": {"country": "India"},
    })
    assert res.status_code == 200
    body = res.json()
    assert body["entity"] == "startup"
    assert body["sources_discovered"] >= 1
    assert "company_name" in body["obtainable"]
    assert len(body["availability"]) == 3
