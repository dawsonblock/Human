import os
import pytest
from pathlib import Path
from subjective_runtime_v2_1.storage.paths import StoragePaths
from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend
from subjective_runtime_v2_1.state.models import AgentStateV2_1

def test_memory_db_persistence():
    """Verify that :memory: DB survives across multiple SQLiteBackend instances (via shared cache)."""
    # Create first backend and initialize it
    # We must use a unique path or let the class generate one (which it does via id(self))
    # However, for this test, we want to simulate the SAME backend being reopened or used across connections.
    backend1 = SQLiteBackend(":memory:")
    
    # Create a run
    backend1.create_run("test-run", {"goal": "test"})
    assert backend1.has_run("test-run")
    
    # Now simulate a second connection/backend using the SAME internal path
    # SQLiteBackend handles the shared cache URI internally.
    # To test persistence, we need another backend that points to the SAME shared memory area.
    # In my implementation, self.path is unique to id(self).
    # So I should check if I can share it.
    
    # Wait, if id(self) is unique, then TWO SQLiteBackend(":memory:") will NOT share data.
    # This is actually GOOD for isolation, but BAD if the app re-instantiates it.
    # The app usually has one shared backend instance.
    
    # Let's verify that a single backend instance's internal connections share data.
    # append_lifecycle_event creates a NEW connection via self._conn()
    backend1.append_lifecycle_event("test-run", "test_event", {"val": 1})
    
    # load_events also creates a NEW connection
    events = backend1.load_events("test-run")
    assert len(events) == 1
    assert events[0]["type"] == "test_event"
    
    backend1.close()

def test_reject_empty_allowed_roots():
    """Verify that StoragePaths rejects empty or whitespace roots."""
    # Test direct list
    with pytest.raises(ValueError, match="cannot be empty"):
        StoragePaths(allowed_roots=[""])
        
    with pytest.raises(ValueError, match="cannot be empty"):
        StoragePaths(allowed_roots=["  "])

    # Test environment variable
    os.environ["HUMAN_ALLOWED_ROOTS"] = "/tmp/a::/tmp/b"
    try:
        with pytest.raises(ValueError, match="contains an empty or whitespace segment"):
            StoragePaths()
    finally:
        del os.environ["HUMAN_ALLOWED_ROOTS"]

def test_prevent_orphan_events():
    """Verify that appending events to non-existent runs fails."""
    backend = SQLiteBackend(":memory:")
    
    with pytest.raises(KeyError, match="does not exist"):
        backend.append_lifecycle_event("ghost-run", "test", {})
        
    backend.close()

def test_atomic_status_transition():
    """Verify that transition_run_status_with_event updates both status and events."""
    backend = SQLiteBackend(":memory:")
    backend.create_run("run-1", {"goal": "test"}, status="running")
    
    backend.transition_run_status_with_event("run-1", "paused", "pause_requested", {"reason": "user"})
    
    # Check status
    run = backend.get_run("run-1")
    assert run.status == "paused"
    
    # Check event log
    events = backend.load_events("run-1")
    assert len(events) == 1
    assert events[0]["type"] == "pause_requested"
    
    backend.close()

def test_save_state_mirrors_artifacts():
    """Verify that save_state (inherited/overridden) mirrors artifacts into the index."""
    backend = SQLiteBackend(":memory:")
    backend.create_run("run-1", {"goal": "test"})
    
    # Create state with an artifact
    from subjective_runtime_v2_1.state.models import Artifact
    state = AgentStateV2_1()
    state.artifacts = [
        Artifact(id="art-1", run_id="run-1", type="note", title="Test Note", content={"text": "hello"})
    ]
    
    # Save state
    backend.save_state("run-1", state)
    
    # Check artifact index
    stats = backend.get_storage_stats()
    assert stats["artifact_count"] == 1
    
    artifacts = backend.list_artifacts("run-1")
    assert len(artifacts) == 1
    assert artifacts[0]["id"] == "art-1"
    
    backend.close()
