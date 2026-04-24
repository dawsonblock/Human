import pytest
from fastapi.testclient import TestClient
from subjective_runtime_v2_1.api.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_api_prefix_is_used(client):
    """
    Test that the backend API routes are correctly mounted under /api.
    """
    # The root /runs endpoint should be 404 (or served by static UI fallback if configured)
    # Actually, the static UI only serves on `/`, so `/runs` should be 404
    response_root = client.get("/runs")
    assert response_root.status_code == 404, "Backend should not register /runs at the root"

    # The /api/runs endpoint should exist and return a valid JSON response
    response_api = client.get("/api/runs")
    assert response_api.status_code == 200, "Backend should serve /api/runs"
    assert "runs" in response_api.json()
