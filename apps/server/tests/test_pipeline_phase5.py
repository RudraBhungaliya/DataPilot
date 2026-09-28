"""
Phase 5 Data Intelligence Pipeline tests.

Covers extraction (deterministic + LLM), normalization, validation,
deduplication, dataset building, export, executor wiring, and the dataset API.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ai.provider import LLMProvider
from app.collection.manager import CollectionManager
from app.collection.schemas import (
    AccessMethod,
    CollectionResult,
    JobStatus,
    RawDocument,
    SourceDefinition,
    SourceType,
)
from app.pipeline.extraction import ExtractionEngine, JSONExtractor, LLMExtractor
from app.pipeline.schemas import ExtractionRecord
from app.pipeline.service import DataPipelineService
from app.pipeline.store import DataStore
from app.pipeline.stages import (
    records_to_csv,
    records_to_json,
    validate_record,
    normalize_data,
    mark_duplicates,
)


class FakeProvider(LLMProvider):
    """LLM provider that returns canned records for extraction tests."""

    def __init__(self, records):
        self.records = records

    async def generate_json(self, prompt, system_prompt, temperature=0.1):
        return {"records": self.records}


def _json_doc(content: str, url: str = "https://example.com/data.json") -> RawDocument:
    return RawDocument(
        document_id="doc_json_1",
        job_id="job_1",
        source_id="src_1",
        url=url,
        canonical_url=url,
        content_type="application/json",
        content=content,
        status_code=200,
    )


# ---------------------------------------------------------------------------
# 1. Extraction
# ---------------------------------------------------------------------------

def test_json_extractor_deterministic():
    content = json.dumps([
        {"company_name": "Acme", "funding": 1000},
        {"company_name": "Beta", "funding": 2000},
    ])
    records = JSONExtractor().extract(content, "startup", ["company_name", "funding"])
    assert len(records) == 2
    assert records[0].data["company_name"] == "Acme"
    assert records[0].extraction_method == "deterministic_json"
    assert records[0].confidence >= 0.8


def test_json_extractor_nested_list_and_invalid():
    assert JSONExtractor().extract("not json", "startup", []) == []
    payload = json.dumps({"results": [{"name": "X"}], "meta": 1})
    records = JSONExtractor().extract(payload, "startup", ["name"])
    assert len(records) == 1 and records[0].data["name"] == "X"


@pytest.mark.asyncio
async def test_extraction_engine_llm_fallback_and_provenance():
    engine = ExtractionEngine(
        llm_extractor=LLMExtractor(provider=FakeProvider([{"company_name": "Gamma", "funding": 5000}]))
    )
    doc = RawDocument(
        document_id="doc_html_1",
        job_id="job_9",
        source_id="src_9",
        url="https://example.com/page",
        canonical_url="https://example.com/page",
        content_type="text/html",
        content="<html><body>Gamma raised 5000</body></html>",
        status_code=200,
    )
    records = await engine.extract_document(doc, "startup", ["company_name", "funding"])
    assert len(records) == 1
    assert records[0].extraction_method == "llm"
    # Provenance is stamped from the source document
    assert records[0].source_document_id == "doc_html_1"
    assert records[0].source_url == "https://example.com/page"
    assert records[0].collection_job_id == "job_9"


@pytest.mark.asyncio
async def test_extraction_engine_skips_llm_when_unconfigured():
    # No injected provider + placeholder key => no LLM call, no records
    engine = ExtractionEngine()
    doc = RawDocument(
        document_id="doc_html_2",
        job_id="j",
        source_id="s",
        url="https://example.com/p",
        canonical_url="https://example.com/p",
        content_type="text/html",
        content="<html>no structured data</html>",
        status_code=200,
    )
    assert await engine.extract_document(doc, "startup", ["company_name"]) == []


# ---------------------------------------------------------------------------
# 2. Normalization / validation / deduplication
# ---------------------------------------------------------------------------

def test_normalize_data():
    normalized = normalize_data({"Company Name": "  Acme   Inc ", "Funding": "1000"})
    assert normalized["company_name"] == "Acme Inc"
    assert normalized["funding"] == "1000"


def test_validate_record_required_and_filters():
    assert validate_record({"company_name": "Acme"}, ["company_name", "funding"]) == [
        "missing_required_field:funding"
    ]
    ok = validate_record({"company_name": "Acme", "funding": 2000}, ["company_name"], [
        {"field": "funding", "operator": "greater_than", "value": 1500}
    ])
    assert ok == []
    failed = validate_record({"company_name": "Acme", "funding": 1000}, ["company_name"], [
        {"field": "funding", "operator": "greater_than", "value": 1500}
    ])
    assert failed == ["filter_failed:funding"]


def test_mark_duplicates():
    records = [
        ExtractionRecord(entity="startup", data={"company_name": "Acme"}),
        ExtractionRecord(entity="startup", data={"company_name": "Acme"}),
        ExtractionRecord(entity="startup", data={"company_name": "Beta"}),
    ]
    removed = mark_duplicates(records, ["company_name"])
    assert removed == 1
    assert records[1].is_duplicate is True
    assert records[0].is_duplicate is False


# ---------------------------------------------------------------------------
# 3. Pipeline service end-to-end + export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_service_end_to_end_and_export():
    docs = [
        _json_doc(json.dumps([
            {"company_name": "Acme", "funding": 1000},
            {"company_name": "Acme", "funding": 1000},
            {"company_name": "Beta"},
        ]))
    ]
    service = DataPipelineService(store=DataStore())

    stats = await service.extract_records("wf_1", "startup", ["company_name", "funding"], docs)
    assert stats.records_extracted == 3

    await service.normalize("wf_1")
    vs = await service.validate("wf_1", ["company_name", "funding"], [])
    assert vs.records_valid == 2 and vs.records_invalid == 1

    ds = await service.deduplicate("wf_1", ["company_name"])
    assert ds.duplicates_removed == 1

    dataset = await service.build_dataset(
        "wf_1", "startup", "Startup Dataset", ["company_name", "funding"], "json"
    )
    assert dataset.record_count == 1
    assert dataset.workflow_id == "wf_1"

    records = await service.list_dataset_records(dataset.id)
    assert len(records) == 1

    export = await service.export_dataset(dataset.id, "json")
    assert export["record_count"] == 1
    assert export["size_bytes"] > 0
    assert Path(export["stored_at"]).exists()


def test_export_serializers():
    records = [ExtractionRecord(entity="startup", data={"company_name": "Acme", "funding": 1000})]
    csv_text = records_to_csv(records, ["company_name", "funding"])
    assert "company_name,funding" in csv_text and "Acme,1000" in csv_text
    json_text = records_to_json(records, ["company_name"])
    assert json.loads(json_text) == [{"company_name": "Acme"}]


# ---------------------------------------------------------------------------
# 4. Full workflow DAG runs the real pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_dag_runs_real_pipeline(monkeypatch):
    from app.workflows.engine import WorkflowEngine
    from app.workflows.planner import WorkflowPlanner
    from app.workflows.registry import get_default_registry
    from app.workflows.types import StepType, StepStatus, WorkflowStatus
    from app.ai.schemas import StructuredRequirement

    # Isolate pipeline state and inject a fake LLM provider
    fresh_service = DataPipelineService(
        store=DataStore(),
        extractor=ExtractionEngine(json_extractor=JSONExtractor(),
                                   llm_extractor=LLMExtractor(provider=FakeProvider([]))),
    )
    monkeypatch.setattr("app.workflows.executors.pipeline.get_data_service", lambda: fresh_service)

    json_content = json.dumps([{"company_name": "Acme", "funding": 1500}])
    raw_doc = RawDocument(
        document_id="doc_wf_json",
        job_id="job_wf_1",
        source_id="src_1",
        url="https://example.com/data.json",
        canonical_url="https://example.com/data.json",
        content_type="application/json",
        content=json_content,
        status_code=200,
    )

    async def fake_execute_job(self, request, sources, **kwargs):
        return CollectionResult(
            job_id="job_wf_1",
            request_id="colreq_wf",
            status=JobStatus.COMPLETED.value,
            documents=[raw_doc.to_reference("storage://documents/doc_wf_json")],
        )

    monkeypatch.setattr(CollectionManager, "execute_job", fake_execute_job)

    req = StructuredRequirement(
        objective="Find AI startups",
        entity="startup",
        required_fields=["company_name", "funding"],
        output_format="json",
    )
    wf = WorkflowPlanner().plan(requirement=req)
    engine = WorkflowEngine(registry=get_default_registry())
    executed = await engine.execute(wf)

    assert executed.status == WorkflowStatus.COMPLETED
    extract_step = [s for s in executed.steps if s.type == StepType.EXTRACT_DATA][0]
    assert extract_step.status == StepStatus.COMPLETED
    assert extract_step.output.get("records_extracted") == 1

    build_step = [s for s in executed.steps if s.type == StepType.BUILD_DATASET][0]
    assert build_step.output.get("record_count") == 1
    dataset_id = build_step.output.get("dataset_id")

    export_step = [s for s in executed.steps if s.type == StepType.EXPORT_DATA][0]
    assert export_step.status == StepStatus.COMPLETED
    assert export_step.output.get("dataset_id") == dataset_id


# ---------------------------------------------------------------------------
# 5. Dataset API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dataset_api_endpoints(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.v1.endpoints.datasets as datasets_module

    service = DataPipelineService(store=DataStore())
    monkeypatch.setattr(datasets_module, "data_service", service)

    docs = [_json_doc(json.dumps([{"company_name": "Acme", "funding": 1000}]))]
    await service.extract_records("wf_api", "startup", ["company_name", "funding"], docs)
    dataset = await service.build_dataset(
        "wf_api", "startup", "API Dataset", ["company_name", "funding"], "json"
    )

    client = TestClient(app)

    listing = client.get("/api/v1/datasets")
    assert listing.status_code == 200
    assert any(d["id"] == dataset.id for d in listing.json())

    detail = client.get(f"/api/v1/datasets/{dataset.id}")
    assert detail.status_code == 200
    assert detail.json()["record_count"] == 1

    records = client.get(f"/api/v1/datasets/{dataset.id}/records")
    assert records.status_code == 200
    assert records.json()["total"] == 1

    export = client.get(f"/api/v1/datasets/{dataset.id}/export/csv")
    assert export.status_code == 200
    assert "company_name" in export.text

    missing = client.get("/api/v1/datasets/does-not-exist")
    assert missing.status_code == 404
