"""Tests for compact state endpoint after a run has produced action history."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    from subjective_runtime_v2_1.api.app import create_app
    app = create_app(
        db_path=str(tmp_path / "test.db"),
        allowed_roots=[str(tmp_path)],
    )
    return TestClient(app)


def test_compact_state_returns_200_before_any_action(client):
    # Create run, immediately fetch compact state — should never raise
    resp = client.post("/api/runs", json={"inputs": {}, "config": {}})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    resp2 = client.get(f"/api/runs/{run_id}/state/compact")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["run_id"] == run_id
    # last_action and last_outcome are None when no action has occurred
    assert data["last_action"] is None
    assert data["last_outcome"] is None


def test_compact_state_does_not_break_when_last_action_is_dict(client, tmp_path):
    """Regression: asdict() on a plain dict raises TypeError.
    Simulate by injecting a dict into state and calling the endpoint."""
    from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
    from subjective_runtime_v2_1.state.models import AgentStateV2_1

    resp = client.post("/api/runs", json={"inputs": {}, "config": {}})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # Directly patch state to contain a plain dict for last_action
    store = SQLiteRunStore(str(tmp_path / "test.db"))
    state = store.load_state(run_id)
    if state is None:
        state = AgentStateV2_1()
    state.last_action = {"tool_name": "echo", "arguments": {"message": "hi"}}
    state.last_outcome = {"status": "ok", "result": {}}
    store.save_state(run_id, state)

    resp2 = client.get(f"/api/runs/{run_id}/state/compact")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["last_action"]["tool_name"] == "echo"
    assert data["last_outcome"]["status"] == "ok"
