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

def test_api_v1_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]
    print("\n[OK] Health endpoint response:", data)

if __name__ == "__main__":
    test_root_redirect()
    test_api_v1_root()
    test_api_v1_health()
    print("\n[SUCCESS] All backend test assertions passed successfully!")
