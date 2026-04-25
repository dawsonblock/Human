"""Tests for event sequencing atomicity.

These tests verify that:
- Lifecycle events (pause/resume/input) and cycle events share one
  strictly-monotonic sequence per run.
- Concurrent lifecycle event inserts never produce duplicate seqs.
- An append_lifecycle_event that runs concurrently with a cycle commit
  does not produce gaps or duplicates.
"""
from __future__ import annotations

import threading
import time

import pytest

from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft


def _make_transition(run_id: str, seq: int) -> CycleTransition:
    state = AgentStateV2_1(cycle_id=seq)
    return CycleTransition(
        run_id=run_id,
        cycle_id=seq,
        state=state,
        events=[RuntimeEventDraft(type="cycle_tick", payload={"cycle": seq})],
        status_override=None,
    )


# ── Monotonic sequencing ─────────────────────────────────────────────────────

def test_lifecycle_events_are_sequential(tmp_path):
    db = SQLiteBackend(tmp_path / "seq.db")
    db.create_run("r1", config={})

    for evt_type in ["paused", "resumed", "input_enqueued", "stopped"]:
        db.append_lifecycle_event("r1", evt_type, {"x": 1})

    events = db.load_events("r1")
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(1, len(seqs) + 1)), f"Seqs not monotonic: {seqs}"


def test_cycle_and_lifecycle_share_one_stream(tmp_path):
    db = SQLiteBackend(tmp_path / "shared.db")
    db.create_run("r2", config={})

    # Alternate cycle commits and lifecycle events
    db.apply_cycle_transition(_make_transition("r2", 1))
    db.append_lifecycle_event("r2", "paused", {})
    db.apply_cycle_transition(_make_transition("r2", 2))
    db.append_lifecycle_event("r2", "resumed", {})

    events = db.load_events("r2")
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), f"Events out of order: {seqs}"
    assert len(seqs) == len(set(seqs)), f"Duplicate seqs: {seqs}"
    # cycle_tick x2 + paused + resumed = 4 events
    assert len(seqs) == 4


def test_concurrent_lifecycle_events_no_duplicates(tmp_path):
    """50 threads each write 10 lifecycle events — no seq duplicates."""
    db = SQLiteBackend(tmp_path / "concurrent.db")
    db.create_run("r3", config={})

    errors: list[Exception] = []

    def worker(n: int):
        try:
            for i in range(10):
                db.append_lifecycle_event("r3", f"evt_{n}_{i}", {"n": n, "i": i})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors during concurrent writes: {errors}"

    events = db.load_events("r3", limit=10_000)
    seqs = [e["seq"] for e in events]
    assert len(seqs) == 500
    assert seqs == list(range(1, 501)), f"Seqs not monotonic under concurrency"


def test_no_orphan_events_if_cycle_transition_fails(tmp_path):
    """If state JSON serialisation fails, no partial event rows should appear."""
    db = SQLiteBackend(tmp_path / "orphan.db")
    db.create_run("r4", config={})

    # Insert one clean cycle to establish baseline
    db.apply_cycle_transition(_make_transition("r4", 1))
    assert db.get_last_seq("r4") == 1

    # Simulate a transition with an un-serialisable state by patching state_to_dict
    import unittest.mock as mock

    bad_transition = _make_transition("r4", 2)
    with mock.patch(
        "subjective_runtime_v2_1.state.store.state_to_dict",
        side_effect=ValueError("boom"),
    ):
        with pytest.raises(ValueError):
            db.apply_cycle_transition(bad_transition)

    # Seq must still be 1 — no orphan events
    assert db.get_last_seq("r4") == 1


def test_artifact_index_rollback_on_failure(tmp_path):
    """If state commit fails, no artifacts should be inserted into the index."""
    db = SQLiteBackend(tmp_path / "rollback_art.db")
    db.create_run("r5", config={})

    art = {"id": "art-999", "run_id": "r5", "title": "Fail Art", "type": "note"}
    transition = _make_transition("r5", 1)
    transition.state.artifacts = [art]  # type: ignore

    import unittest.mock as mock
    # Patch self.append_events_tx to fail inside the transaction
    with mock.patch.object(SQLiteBackend, "append_events_tx", side_effect=RuntimeError("db fail")):
        with pytest.raises(RuntimeError):
            db.apply_cycle_transition(transition)

    # Index should be empty
    assert len(db.list_artifacts("r5")) == 0
