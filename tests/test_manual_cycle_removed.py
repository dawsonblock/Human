"""Test that the manual cycle bypass endpoint no longer exists.

Acceptance criterion: there must be no /runs/{run_id}/cycle route.
Any debug tick must go through the supervisor (via input injection or the
supervisor's own lock).
"""
from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from subjective_runtime_v2_1.api.app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    return TestClient(app, raise_server_exceptions=False)


def test_manual_cycle_endpoint_removed(client):
    """POST /runs/{run_id}/cycle must return 404 or 405, not 200."""
    # Create a run first
    resp = client.post("/api/runs", json={"inputs": {}, "config": {}})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    cycle_resp = client.post(f"/api/runs/{run_id}/cycle", json={"inputs": {}})
    assert cycle_resp.status_code in (404, 405), (
        f"Expected 404/405 (endpoint removed), got {cycle_resp.status_code}"
    )


def test_no_cycle_path_in_routes(tmp_path):
    """The router must not expose any path ending in /cycle."""
    from subjective_runtime_v2_1.api.routes import build_router
    from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
    from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
    from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
    from subjective_runtime_v2_1.action.executor import Executor
    from subjective_runtime_v2_1.action.gate import ActionGate
    from subjective_runtime_v2_1.action.tools import build_tool_registry
    from subjective_runtime_v2_1.runtime.core import RuntimeCore
    from subjective_runtime_v2_1.state.store import InMemoryStateStore

    db = SQLiteRunStore(tmp_path / "routes.db")
    em = EventManager(db, LiveEventBus())
    reg = build_tool_registry(allowed_roots=["."])

    def rf():
        return RuntimeCore(InMemoryStateStore(), ActionGate(reg), Executor(reg))

    router = build_router(rf, RuntimeScheduler(rf, em, db), db, em)
    paths = [route.path for route in router.routes]
    cycle_paths = [p for p in paths if p.endswith("/cycle")]
    assert cycle_paths == [], f"Unexpected /cycle route(s): {cycle_paths}"


def test_approve_endpoint_exists(client):
    resp = client.post("/api/runs", json={"inputs": {}, "config": {}})
    run_id = resp.json()["run_id"]

    # Should return 404 (no pending request), not 405 (method not allowed)
    resp = client.post(f"/api/runs/{run_id}/approve", json={"action_id": "nonexistent"})
    assert resp.status_code != 405, "approve endpoint must exist"


def test_deny_endpoint_exists(client):
    resp = client.post("/api/runs", json={"inputs": {}, "config": {}})
    run_id = resp.json()["run_id"]

    resp = client.post(f"/api/runs/{run_id}/deny", json={"action_id": "nonexistent"})
    assert resp.status_code != 405, "deny endpoint must exist"
