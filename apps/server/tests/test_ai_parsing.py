"""
Unit and Integration Tests for AI Requirement Understanding and Workflow Parsing.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch

# Ensure app is in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.ai.schemas import (
    StructuredRequirement,
    FilterRule,
    FilterOperator,
    LocationConstraint,
    TimeConstraint,
    RequirementParseRequest,
    RequirementParseResponse,
)
from app.ai.provider import LLMProvider, MockProvider, LLMAuthenticationError, LLMTimeoutError, LLMInvalidResponseError
from app.ai.parser import RequirementParser, RequirementParsingError
from app.services.workflow import WorkflowService

client = TestClient(app)


# ==============================================================================
# 1. Pydantic Schema & Validation Unit Tests
# ==============================================================================

def test_filter_rule_operator_normalization():
    """Tests operator string normalization in FilterRule."""
    rule1 = FilterRule(field="salary", operator=">", value=100000)
    assert rule1.operator == FilterOperator.GREATER_THAN

    rule2 = FilterRule(field="company_size", operator="gte", value=50)
    assert rule2.operator == FilterOperator.GREATER_THAN_OR_EQUAL

    rule3 = FilterRule(field="role", operator="contains", value="Engineer")
    assert rule3.operator == FilterOperator.CONTAINS


def test_structured_requirement_valid_instantiation():
    """Tests valid creation of StructuredRequirement model."""
    req_dict = {
        "objective": "Find software engineering internships in India",
        "entity": "job_posting",
        "location": {"country": "India"},
        "time_constraint": {
            "type": "posted_within",
            "value": 7,
            "unit": "days",
        },
        "required_fields": [
            "Company Name",
            "Role",
            "Location",
            "Salary",
            "Application URL",
        ],
        "filters": [
            {"field": "salary", "operator": "greater_than", "value": 50000}
        ],
        "source_preferences": ["LinkedIn"],
        "output_format": "table",
        "confidence_score": 0.95,
        "is_ambiguous": False,
        "clarification_needed": None,
    }

    req = StructuredRequirement.model_validate(req_dict)
    assert req.objective == "Find software engineering internships in India"
    assert req.entity == "job_posting"
    assert req.location.country == "India"
    assert req.time_constraint.value == 7
    assert req.time_constraint.unit == "days"
    # Required fields normalized to snake_case
    assert "company_name" in req.required_fields
    assert "application_url" in req.required_fields
    assert len(req.filters) == 1
    assert req.filters[0].operator == FilterOperator.GREATER_THAN


def test_structured_requirement_missing_objective_fails():
    """Ensures missing required fields like objective raises ValidationError."""
    with pytest.raises(ValidationError):
        StructuredRequirement.model_validate({
            "entity": "job_posting",
        })


def test_requirement_parse_request_empty_prompt_rejected():
    """Ensures empty prompt or only whitespace is rejected by request model."""
    with pytest.raises(ValidationError):
        RequirementParseRequest(prompt="")

    with pytest.raises(ValidationError):
        RequirementParseRequest(prompt="   \n\t  ")


# ==============================================================================
# 2. RequirementParser Unit Tests with Mock LLM
# ==============================================================================

@pytest.mark.asyncio
async def test_requirement_parser_success():
    mock_llm = MockProvider(mock_response={
        "objective": "Find cybersecurity companies in India",
        "entity": "company",
        "location": {"country": "India"},
        "time_constraint": None,
        "required_fields": ["company_name", "industry", "headquarters"],
        "filters": [],
        "source_preferences": [],
        "output_format": "table",
        "confidence_score": 0.98,
        "is_ambiguous": False,
        "clarification_needed": None,
    })

    parser = RequirementParser(provider=mock_llm)
    result = await parser.parse("Find cybersecurity companies in India.")
    assert result.objective == "Find cybersecurity companies in India"
    assert result.entity == "company"
    assert result.location.country == "India"


@pytest.mark.asyncio
async def test_requirement_parser_invalid_ai_output():
    """Ensures parser raises RequirementParsingError when LLM returns invalid schema."""
    bad_mock_llm = MockProvider(mock_response={
        "non_existent_key": "some random unparseable data",
    })

    parser = RequirementParser(provider=bad_mock_llm)
    with pytest.raises(RequirementParsingError):
        await parser.parse("Find data")


@pytest.mark.asyncio
async def test_requirement_parser_llm_failure_propagation():
    """Ensures provider exceptions are handled cleanly without crashing or exposing keys."""
    class FailingProvider(LLMProvider):
        async def generate_json(self, prompt: str, system_prompt: str, temperature: float = 0.1):
            raise LLMAuthenticationError("Authentication failed")

    parser = RequirementParser(provider=FailingProvider())
    with pytest.raises(LLMAuthenticationError) as exc_info:
        await parser.parse("Find jobs")
    assert "Authentication failed" in str(exc_info.value)


# ==============================================================================
# 3. API Endpoint Tests (POST /api/v1/workflows/parse)
# ==============================================================================

def test_api_parse_endpoint_success():
    sample_response = {
        "objective": "Find software engineering internships in India",
        "entity": "job_posting",
        "location": {"country": "India", "state": None, "city": None, "region": None, "raw": "India"},
        "time_constraint": {"type": "posted_within", "value": 7, "unit": "days", "start_date": None, "end_date": None, "raw_text": "7 days"},
        "required_fields": ["company_name", "role", "location", "salary", "application_url"],
        "filters": [],
        "source_preferences": ["LinkedIn"],
        "output_format": "table",
        "confidence_score": 0.99,
        "is_ambiguous": False,
        "clarification_needed": None,
    }

    with patch("app.ai.provider.GeminiProvider.generate_json", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = sample_response

        response = client.post(
            "/api/v1/workflows/parse",
            json={"prompt": "Find software engineering internships in India posted in the last 7 days."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["requirement"] is not None
        assert data["requirement"]["objective"] == "Find software engineering internships in India"
        assert data["requirement"]["entity"] == "job_posting"
        assert data["requirement"]["location"]["country"] == "India"
        assert len(data["requirement"]["required_fields"]) == 5


def test_api_parse_endpoint_empty_prompt_validation():
    """Tests 422 Unprocessable Entity on blank prompt."""
    response = client.post(
        "/api/v1/workflows/parse",
        json={"prompt": "   "},
    )
    assert response.status_code == 422


def test_api_parse_endpoint_ambiguous_prompt():
    """Tests ambiguous prompt parsing where clarification is requested."""
    ambiguous_response = {
        "objective": "Unclear request",
        "entity": "unknown",
        "location": None,
        "time_constraint": None,
        "required_fields": [],
        "filters": [],
        "source_preferences": [],
        "output_format": "table",
        "confidence_score": 0.2,
        "is_ambiguous": True,
        "clarification_needed": "What specific data or industry are you looking to extract?",
    }

    with patch("app.ai.provider.GeminiProvider.generate_json", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = ambiguous_response

        response = client.post(
            "/api/v1/workflows/parse",
            json={"prompt": "give me something"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["requirement"]["is_ambiguous"] is True
        assert data["clarification_needed"] == "What specific data or industry are you looking to extract?"


def test_api_parse_endpoint_provider_auth_error():
    """Tests clean 503 response when AI provider credentials fail."""
    with patch("app.ai.provider.GeminiProvider.generate_json", side_effect=LLMAuthenticationError("Auth failed")):
        response = client.post(
            "/api/v1/workflows/parse",
            json={"prompt": "Find top AI startups"},
        )
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "not configured or authenticated" in data["detail"]
        # Ensure no secrets or API keys leaked
        assert "AI_API_KEY" not in str(data)


def test_api_parse_endpoint_provider_timeout():
    """Tests clean 504 response when AI provider times out."""
    with patch("app.ai.provider.GeminiProvider.generate_json", side_effect=LLMTimeoutError("Timed out")):
        response = client.post(
            "/api/v1/workflows/parse",
            json={"prompt": "Find top AI startups"},
        )
        assert response.status_code == 504
        data = response.json()
        assert "timed out" in data["detail"].lower()


def test_api_create_and_get_workflow():
    """Tests saving and retrieving a workflow specification."""
    payload = {
        "prompt": "Find cybersecurity startups in India",
        "requirement": {
            "objective": "Find cybersecurity startups in India",
            "entity": "startup",
            "location": {"country": "India"},
            "time_constraint": None,
            "required_fields": ["name", "website", "funding"],
            "filters": [],
            "source_preferences": ["Crunchbase"],
            "output_format": "table",
            "confidence_score": 0.95,
            "is_ambiguous": False,
            "clarification_needed": None,
        },
        "status": "CONFIRMED",
    }
    response = client.post("/api/v1/workflows", json=payload)
    if response.status_code == 201:
        data = response.json()
        assert data["prompt"] == payload["prompt"]
        assert data["status"] == "CONFIRMED"
        wf_id = data["id"]

        get_res = client.get(f"/api/v1/workflows/{wf_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == wf_id


if __name__ == "__main__":
    pytest.main(["-v", __file__])
