"""Tests for atomic state+event persistence via apply_cycle_transition.

Acceptance criterion from the problem statement:
  "Kill the process at arbitrary points during a cycle. After restart, you
   should never see persisted events that describe a cycle whose state was not
   committed, and never see a committed state whose cycle events are missing."

These tests validate the SQLiteRunStore.apply_cycle_transition contract and
verify that supervisor-driven cycles produce consistent state+event records.
"""
from __future__ import annotations

import asyncio

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.runtime.supervisor import RunConfig
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry():
    return build_tool_registry(allowed_roots=["."])


def _make_runtime():
    registry = _make_registry()
    return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))


# ---------------------------------------------------------------------------
# apply_cycle_transition
# ---------------------------------------------------------------------------

def test_apply_cycle_transition_atomicity(tmp_path):
    """State and events from the same cycle are always in sync."""
    db = SQLiteRunStore(tmp_path / "runtime.db")
    db.create_run("r1", config={}, status="running")

    runtime = _make_runtime()
    result = runtime.cycle("r1", {"text": "hello"})

    committed = db.apply_cycle_transition("r1", result.new_state, result.events)

    # Events were written
    assert len(committed) == len(result.events)
    persisted = db.load_events("r1")
    assert len(persisted) == len(result.events)

    # Seqs are strictly monotonic
    seqs = [e["seq"] for e in persisted]
    assert seqs == list(range(1, len(seqs) + 1))

    # State matches
    loaded_state = db.load_state("r1")
    assert loaded_state.cycle_id == result.new_state.cycle_id


def test_apply_cycle_transition_no_phantom_events(tmp_path):
    """If apply_cycle_transition is never called, no events appear in DB."""
    db = SQLiteRunStore(tmp_path / "runtime.db")
    db.create_run("r2", config={}, status="running")

    runtime = _make_runtime()
    # Run a cycle but do NOT call apply_cycle_transition
    runtime.cycle("r2", {"text": "silent"})

    persisted = db.load_events("r2")
    # No events should be in the DB
    assert persisted == []


def test_apply_cycle_transition_multi_cycle_monotonic_seqs(tmp_path):
    """Across multiple cycles, event seqs are globally monotonic for the run."""
    db = SQLiteRunStore(tmp_path / "runtime.db")
    db.create_run("r3", config={}, status="running")

    runtime = _make_runtime()
    for i in range(3):
        result = runtime.cycle("r3", {"text": f"cycle {i}"})
        db.apply_cycle_transition("r3", result.new_state, result.events)

    all_events = db.load_events("r3", limit=1000)
    seqs = [e["seq"] for e in all_events]
    assert seqs == list(range(1, len(seqs) + 1)), "event seqs not monotonic"


def test_apply_cycle_transition_state_version_advances(tmp_path):
    """Cycle IDs in the persisted state advance strictly each call."""
    db = SQLiteRunStore(tmp_path / "runtime.db")
    db.create_run("r4", config={}, status="running")

    runtime = _make_runtime()
    prev_cycle_id = 0
    for _ in range(4):
        result = runtime.cycle("r4", {})
        db.apply_cycle_transition("r4", result.new_state, result.events)
        state = db.load_state("r4")
        assert state.cycle_id > prev_cycle_id
        prev_cycle_id = state.cycle_id


def test_cycle_result_contains_required_events(tmp_path):
    """CycleResult.events always includes cycle_completed and state_updated."""
    runtime = _make_runtime()
    result = runtime.cycle("r5", {"text": "test"})

    event_types = [et for et, _ in result.events]
    assert "cycle_completed" in event_types
    assert "state_updated" in event_types


# ---------------------------------------------------------------------------
# Supervisor integration: state+events must be consistent after a real run
# ---------------------------------------------------------------------------

async def _supervisor_cycle_consistency(db_path):
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())

    def runtime_factory():
        return RuntimeCore(InMemoryStateStore(), ActionGate(_make_registry()), Executor(_make_registry()))

    scheduler = RuntimeScheduler(runtime_factory, events, db)
    supervisor = await scheduler.create_run("sv1", RunConfig(tick_interval_sec=0.02), {"text": "start"})
    await asyncio.sleep(0.12)
    await supervisor.stop()

    state = db.load_state("sv1")
    all_events = db.load_events("sv1", limit=1000)

    # Every persisted cycle_completed event should reference a cycle_id <= state.cycle_id
    cycle_completed = [e for e in all_events if e["type"] == "cycle_completed"]
    for ev in cycle_completed:
        assert ev["payload"]["cycle_id"] <= state.cycle_id

    # Event seqs are monotonically increasing
    seqs = [e["seq"] for e in all_events]
    assert seqs == list(range(1, len(seqs) + 1))


def test_supervisor_cycle_consistency(tmp_path):
    asyncio.run(_supervisor_cycle_consistency(tmp_path / "runtime.db"))
