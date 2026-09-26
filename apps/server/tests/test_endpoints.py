import sys
from pathlib import Path

# Add app to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_redirect():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in [307, 308]
    assert response.headers["location"] == "/docs"

def test_api_v1_root():
    response = client.get("/api/v1/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DataPilot"
    assert data["version"] == "0.1.0"
    assert data["status"] == "operational"
    assert data["health_url"] == "/api/v1/health"

from unittest.mock import patch, AsyncMock

def test_api_v1_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]
    print("\n[OK] Health endpoint response:", data)

def test_api_v1_workflows_parse():
    mock_spec = {
        "objective": "Find software engineering internships in India",
        "entity": "job_posting",
        "location": {"country": "India"},
        "time_constraint": {"type": "posted_within", "value": 7, "unit": "days"},
        "required_fields": ["company_name", "role", "location", "salary", "application_url"],
        "filters": [],
        "source_preferences": [],
        "output_format": "table",
        "confidence_score": 0.98,
        "is_ambiguous": False,
        "clarification_needed": None,
    }
    with patch("app.ai.provider.GeminiProvider.generate_json", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_spec
        response = client.post(
            "/api/v1/workflows/parse",
            json={"prompt": "Find software engineering internships in India posted in the last 7 days"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["requirement"]["entity"] == "job_posting"
        assert len(data["requirement"]["required_fields"]) == 5
        print("\n[OK] Workflows parse endpoint response:", data)

if __name__ == "__main__":
    test_root_redirect()
    test_api_v1_root()
    test_api_v1_health()
    test_api_v1_workflows_parse()
    print("\n[SUCCESS] All backend test assertions passed successfully!")
