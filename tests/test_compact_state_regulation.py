import pytest
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.api.app import create_app
from fastapi.testclient import TestClient

@pytest.fixture
def app_and_client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)
    
    # Create a test run
    db = SQLiteRunStore(db_path)
    run_id = "test_run_1"
    db.create_run(run_id, config={}, status="running")
    state = AgentStateV2_1()
    state.regulation["uncertainty_load"] = 0.8
    state.regulation["continuity_health"] = 0.9
    state.regulation["goal_drift"] = 0.1
    state.regulation["overload_pressure"] = 0.5
    db.save_state(run_id, state)
    
    return client, run_id

def test_compact_state_regulation(app_and_client):
    client, run_id = app_and_client
    response = client.get(f"/api/runs/{run_id}/state/compact")
    assert response.status_code == 200
    data = response.json()
    
    assert "regulation" in data
    reg = data["regulation"]
    assert reg["uncertainty_load"] == 0.8
    assert reg["continuity_health"] == 0.9
    assert reg["goal_drift"] == 0.1
    assert reg["overload_pressure"] == 0.5
