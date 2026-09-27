"""
Comprehensive Unit and Integration Tests for Phase 3 Workflow Engine.
Tests:
- Schema validation
- Workflow planner
- Conditional step generation
- Dependency validation & missing dependency detection
- Circular dependency detection
- Topological execution order
- Executor registry
- Mock executors
- Successful & failed workflow execution
- API endpoints (/plan, /{id}/execute, /{id}, /{id}/steps)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.ai.schemas import StructuredRequirement, OutputFormat, LocationConstraint, TimeConstraint, FilterRule, FilterOperator
from app.workflows.types import WorkflowStatus, StepStatus, StepType
from app.workflows.schemas import WorkflowStep, WorkflowDefinition
from app.workflows.validator import WorkflowValidator, WorkflowValidationError
from app.workflows.planner import WorkflowPlanner
from app.workflows.executors.base import BaseStepExecutor, ExecutionContext, StepResult
from app.workflows.executors.mock import MockStepExecutor
from app.workflows.registry import ExecutorRegistry, get_default_registry, UnknownStepTypeError
from app.workflows.engine import WorkflowEngine
from app.db.session import get_db


@pytest.fixture(autouse=True)
def mock_db_session():
    storage = {}

    class MockAsyncSession:
        def __init__(self):
            self.storage = storage

        def add(self, obj):
            if hasattr(obj, "id"):
                self.storage[obj.id] = obj

        async def commit(self):
            pass

        async def rollback(self):
            pass

        async def refresh(self, obj):
            pass

        async def execute(self, statement):
            matched = []
            target_id = None
            try:
                compiled = statement.compile()
                for k, v in compiled.params.items():
                    if "id" in k.lower() and isinstance(v, str):
                        target_id = v
                        break
            except Exception:
                pass

            if target_id and target_id in self.storage:
                matched = [self.storage[target_id]]
            elif not target_id:
                matched = list(self.storage.values())

            class MockResult:
                def __init__(self, data):
                    self._data = data

                def scalar_one_or_none(self):
                    return self._data[0] if self._data else None

                def scalars(self):
                    class Scalars:
                        def __init__(self, items):
                            self._items = items

                        def all(self):
                            return self._items

                    return Scalars(self._data)

            return MockResult(matched)

    async def override_get_db():
        yield MockAsyncSession()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 1. Schema Validation Tests
# ---------------------------------------------------------------------------

def test_workflow_step_schema():
    step = WorkflowStep(
        id="step_1",
        name="Discover Sources",
        type=StepType.DISCOVER_SOURCES,
        description="Find sources",
        order=1,
        depends_on=[],
        config={"entity": "job_posting"},
    )
    assert step.id == "step_1"
    assert step.status == StepStatus.PENDING
    assert step.depends_on == []
    assert step.config == {"entity": "job_posting"}


def test_workflow_definition_schema():
    step = WorkflowStep(
        id="step_1",
        name="Discover Sources",
        type=StepType.DISCOVER_SOURCES,
        description="Find sources",
        order=1,
    )
    wf = WorkflowDefinition(
        workflow_id="wf-test-123",
        name="Test Workflow",
        description="Test Desc",
        status=WorkflowStatus.PLANNED,
        input_requirement={"entity": "job_posting", "objective": "test"},
        steps=[step],
    )
    assert wf.workflow_id == "wf-test-123"
    assert len(wf.steps) == 1
    assert wf.status == WorkflowStatus.PLANNED


# ---------------------------------------------------------------------------
# 2. Workflow Planner Tests
# ---------------------------------------------------------------------------

def test_planner_generates_valid_workflow():
    req = StructuredRequirement(
        objective="Find software engineering internships in India",
        entity="job_posting",
        location=LocationConstraint(country="India"),
        time_constraint=TimeConstraint(type="posted_within", value=7, unit="days"),
        required_fields=["company_name", "role", "location", "salary", "application_url"],
        filters=[],
        source_preferences=["LinkedIn"],
        output_format=OutputFormat.TABLE,
    )
    planner = WorkflowPlanner()
    wf = planner.plan(requirement=req, prompt="Find internships in India")

    assert wf.name == "Job Posting Intelligence Collection"
    assert wf.status == WorkflowStatus.PLANNED
    assert len(wf.steps) >= 7

    types = [s.type for s in wf.steps]
    assert StepType.DISCOVER_SOURCES in types
    assert StepType.COLLECT_DATA in types
    assert StepType.EXTRACT_DATA in types
    assert StepType.NORMALIZE_DATA in types
    assert StepType.VALIDATE_DATA in types
    assert StepType.DEDUPLICATE_DATA in types
    assert StepType.BUILD_DATASET in types
    # Since output format is table, EXPORT_DATA should not be present
    assert StepType.EXPORT_DATA not in types


def test_planner_conditional_export_step():
    req = StructuredRequirement(
        objective="Export fintech startups in CSV",
        entity="startup",
        required_fields=["company_name", "founded_year", "website"],
        output_format=OutputFormat.CSV,
    )
    planner = WorkflowPlanner()
    wf = planner.plan(requirement=req)

    types = [s.type for s in wf.steps]
    assert StepType.BUILD_DATASET in types
    assert StepType.EXPORT_DATA in types

    export_step = [s for s in wf.steps if s.type == StepType.EXPORT_DATA][0]
    build_step = [s for s in wf.steps if s.type == StepType.BUILD_DATASET][0]
    assert build_step.id in export_step.depends_on
    assert export_step.config["format"] == "csv"


# ---------------------------------------------------------------------------
# 3. Dependency Validation & Cycle Detection Tests
# ---------------------------------------------------------------------------

def test_dependency_validation_missing_step_rejected():
    step_1 = WorkflowStep(
        id="step_1",
        name="Step 1",
        type=StepType.DISCOVER_SOURCES,
        description="Step 1",
        order=1,
        depends_on=[],
    )
    step_3 = WorkflowStep(
        id="step_3",
        name="Step 3",
        type=StepType.COLLECT_DATA,
        description="Step 3",
        order=2,
        depends_on=["step_99"],  # Non-existent dependency
    )
    wf = WorkflowDefinition(
        workflow_id="wf-invalid",
        name="Invalid WF",
        description="Desc",
        input_requirement={"entity": "test"},
        steps=[step_1, step_3],
    )

    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowValidator.validate(wf)
    assert "depends on non-existent step 'step_99'" in str(exc_info.value)


def test_circular_dependency_rejected():
    # step_1 -> step_2 and step_2 -> step_1
    step_1 = WorkflowStep(
        id="step_1",
        name="Step 1",
        type=StepType.DISCOVER_SOURCES,
        description="Step 1",
        order=1,
        depends_on=["step_2"],
    )
    step_2 = WorkflowStep(
        id="step_2",
        name="Step 2",
        type=StepType.COLLECT_DATA,
        description="Step 2",
        order=2,
        depends_on=["step_1"],
    )
    wf = WorkflowDefinition(
        workflow_id="wf-circular",
        name="Circular WF",
        description="Desc",
        input_requirement={"entity": "test"},
        steps=[step_1, step_2],
    )

    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowValidator.validate(wf)
    assert "Circular dependency detected" in str(exc_info.value)


def test_self_dependency_rejected():
    step_1 = WorkflowStep(
        id="step_1",
        name="Step 1",
        type=StepType.DISCOVER_SOURCES,
        description="Step 1",
        order=1,
        depends_on=["step_1"],
    )
    wf = WorkflowDefinition(
        workflow_id="wf-self",
        name="Self Dep WF",
        description="Desc",
        input_requirement={"entity": "test"},
        steps=[step_1],
    )

    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowValidator.validate(wf)
    assert "cannot depend on itself" in str(exc_info.value)


def test_empty_workflow_rejected():
    wf = WorkflowDefinition.model_construct(
        workflow_id="wf-empty",
        name="Empty WF",
        description="Desc",
        input_requirement={"entity": "test"},
        steps=[],
    )
    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowValidator.validate(wf)
    assert "must contain at least one step" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Topological Execution Order Tests
# ---------------------------------------------------------------------------

def test_topological_execution_order():
    # step_1 (depends_on: [])
    # step_2 (depends_on: ["step_1"])
    # step_3 (depends_on: ["step_2"])
    step_1 = WorkflowStep(id="step_1", name="Step 1", type=StepType.DISCOVER_SOURCES, description="d", order=1, depends_on=[])
    step_2 = WorkflowStep(id="step_2", name="Step 2", type=StepType.COLLECT_DATA, description="d", order=2, depends_on=["step_1"])
    step_3 = WorkflowStep(id="step_3", name="Step 3", type=StepType.EXTRACT_DATA, description="d", order=3, depends_on=["step_2"])

    wf = WorkflowDefinition(
        workflow_id="wf-dag",
        name="DAG WF",
        description="Desc",
        input_requirement={"entity": "test"},
        steps=[step_3, step_1, step_2],  # Given out of order intentionally
    )

    order = WorkflowValidator.validate(wf)
    assert order == ["step_1", "step_2", "step_3"]


# ---------------------------------------------------------------------------
# 5. Executor Registry Tests
# ---------------------------------------------------------------------------

def test_executor_registry_lookup_and_unknown():
    registry = ExecutorRegistry()
    mock_exec = MockStepExecutor()
    registry.register(StepType.COLLECT_DATA, mock_exec)

    assert registry.has(StepType.COLLECT_DATA) is True
    assert registry.has(StepType.DISCOVER_SOURCES) is False
    assert registry.get(StepType.COLLECT_DATA) == mock_exec

    with pytest.raises(UnknownStepTypeError):
        registry.get(StepType.DISCOVER_SOURCES)


from app.workflows.registry import get_mock_registry
from app.workflows.executors.discovery import SourceDiscoveryStepExecutor
from app.workflows.executors.collection import CollectionStepExecutor


def test_default_registry_contains_all_step_types():
    reg = get_default_registry()
    for st in StepType:
        assert reg.has(st) is True

    # Phase 4 binds real discovery and collection executors
    assert isinstance(reg.get(StepType.DISCOVER_SOURCES), SourceDiscoveryStepExecutor)
    assert isinstance(reg.get(StepType.COLLECT_DATA), CollectionStepExecutor)
    assert isinstance(reg.get(StepType.BUILD_DATASET), MockStepExecutor)

    # get_mock_registry binds mock executors for all step types
    mock_reg = get_mock_registry()
    for st in StepType:
        assert isinstance(mock_reg.get(st), MockStepExecutor)


# ---------------------------------------------------------------------------
# 6. Mock Executor Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_executor_all_step_types():
    mock_exec = MockStepExecutor()
    req = StructuredRequirement(
        objective="Find AI engineer jobs",
        entity="job_posting",
        required_fields=["company_name", "role", "salary"],
        filters=[FilterRule(field="salary", operator=FilterOperator.GREATER_THAN, value=100000)],
        output_format=OutputFormat.CSV,
    )
    context = ExecutionContext(
        workflow_id="wf-mock-test",
        input_requirement=req,
    )

    for step_type in StepType:
        step = WorkflowStep(
            id=f"step_{step_type.value.lower()}",
            name=f"Mock {step_type.value}",
            type=step_type,
            description="Mock step",
            order=1,
            config={"format": "csv", "source_preferences": ["LinkedIn"]},
        )
        res = await mock_exec.execute(step=step, context=context)
        assert res.success is True
        assert res.output is not None
        assert res.output.get("is_mock") is True
        assert "MOCK DATA ONLY" in res.output.get("mock_notice", "")


# ---------------------------------------------------------------------------
# 7. Workflow Execution Engine Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_engine_successful_execution():
    req = StructuredRequirement(
        objective="Find software engineering internships in India",
        entity="job_posting",
        required_fields=["company_name", "role", "location", "salary", "application_url"],
        output_format=OutputFormat.TABLE,
    )
    planner = WorkflowPlanner()
    wf = planner.plan(requirement=req)

    engine = WorkflowEngine(registry=get_mock_registry())
    executed_wf = await engine.execute(wf)

    assert executed_wf.status == WorkflowStatus.COMPLETED
    assert executed_wf.error is None
    for step in executed_wf.steps:
        assert step.status == StepStatus.COMPLETED
        assert step.output is not None
        assert step.output.get("is_mock") is True


@pytest.mark.asyncio
async def test_workflow_engine_failed_step_halts_dependent_steps():
    # Create a custom executor that fails on COLLECT_DATA
    class FailingExecutor(BaseStepExecutor):
        async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
            return StepResult(success=False, error="Simulated network failure on collector")

    custom_registry = get_default_registry()
    custom_registry.register(StepType.COLLECT_DATA, FailingExecutor())

    req = StructuredRequirement(
        objective="Test failure flow",
        entity="job_posting",
        required_fields=["company_name"],
    )
    planner = WorkflowPlanner()
    wf = planner.plan(requirement=req)

    engine = WorkflowEngine(registry=custom_registry)
    executed_wf = await engine.execute(wf)

    assert executed_wf.status == WorkflowStatus.FAILED
    assert "Simulated network failure on collector" in str(executed_wf.error)

    # step_1 (DISCOVER_SOURCES) should be COMPLETED
    step_1 = [s for s in executed_wf.steps if s.id == "step_1"][0]
    assert step_1.status == StepStatus.COMPLETED

    # step_2 (COLLECT_DATA) should be FAILED
    step_2 = [s for s in executed_wf.steps if s.id == "step_2"][0]
    assert step_2.status == StepStatus.FAILED

    # Remaining dependent steps (step_3, step_4, etc.) should be SKIPPED
    step_3 = [s for s in executed_wf.steps if s.id == "step_3"][0]
    assert step_3.status == StepStatus.SKIPPED


# ---------------------------------------------------------------------------
# 8. API Endpoints Integration Tests
# ---------------------------------------------------------------------------

client = TestClient(app)

def test_api_workflows_plan():
    req_payload = {
        "requirement": {
            "objective": "Find software engineering internships in India",
            "entity": "job_posting",
            "location": {"country": "India"},
            "time_constraint": {"type": "posted_within", "value": 7, "unit": "days"},
            "required_fields": ["company_name", "role", "location", "salary", "application_url"],
            "filters": [],
            "source_preferences": ["LinkedIn"],
            "output_format": "table",
        },
        "prompt": "Find internships in India posted in last 7 days",
    }
    response = client.post("/api/v1/workflows/plan", json=req_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["workflow"]["name"] == "Job Posting Intelligence Collection"
    assert len(data["workflow"]["steps"]) >= 7


def test_api_workflows_execute_and_get():
    from app.api.v1.endpoints.workflows import workflow_service
    with patch.object(workflow_service, "engine", WorkflowEngine(registry=get_mock_registry())):
        # 1. Plan a workflow
        req_payload = {
            "requirement": {
                "objective": "Find AI research labs",
                "entity": "research_lab",
                "required_fields": ["lab_name", "institution", "director"],
                "output_format": "json",
            },
            "prompt": "Find AI research labs",
        }
        plan_res = client.post("/api/v1/workflows/plan", json=req_payload)
        assert plan_res.status_code == 200
        workflow_id = plan_res.json()["workflow"]["workflow_id"]

        # 2. Get workflow before execute
        get_res = client.get(f"/api/v1/workflows/{workflow_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == workflow_id
        assert get_res.json()["status"] == "PLANNED"

        # 3. Get steps before execute
        steps_res = client.get(f"/api/v1/workflows/{workflow_id}/steps")
        assert steps_res.status_code == 200
        assert len(steps_res.json()["steps"]) > 0

        # 4. Execute workflow
        exec_res = client.post(f"/api/v1/workflows/{workflow_id}/execute")
        assert exec_res.status_code == 200
        exec_data = exec_res.json()
        assert exec_data["success"] is True
        assert exec_data["workflow"]["status"] == "COMPLETED"

        # 5. Get workflow after execute
        get_after_res = client.get(f"/api/v1/workflows/{workflow_id}")
        assert get_after_res.status_code == 200
        assert get_after_res.json()["status"] == "COMPLETED"


def test_api_workflows_not_found():
    response = client.get("/api/v1/workflows/non-existent-id-999")
    assert response.status_code == 404

    exec_response = client.post("/api/v1/workflows/non-existent-id-999/execute")
    assert exec_response.status_code == 404
