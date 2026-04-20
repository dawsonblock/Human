"""Test that events and state stay aligned across simulated crash/restart scenarios.

Acceptance criterion: after simulated interrupted operation around a cycle
commit, event/state consistency is maintained on restart.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.runtime.supervisor import RunConfig
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def _make_runtime():
    reg = build_tool_registry(allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(reg), Executor(reg))


def _make_scheduler(db_path):
    db = SQLiteRunStore(db_path)
    em = EventManager(db, LiveEventBus())
    reg = build_tool_registry(allowed_roots=["."])

    class StateSeeder:
        def load(self, run_id):
            state = db.load_state(run_id)
            if state is None:
                db.create_run(run_id, config={}, status="running")
                state = db.load_state(run_id)
            return state

        def save(self, run_id, state):
            db.save_state(run_id, state)

    def rf():
        return RuntimeCore(StateSeeder(), ActionGate(reg), Executor(reg))

    return RuntimeScheduler(rf, em, db), db, em


# ---------------------------------------------------------------------------
# Scenario 1: cycle computed but transition never committed (pre-commit crash)
# ---------------------------------------------------------------------------

def test_pre_commit_crash_leaves_clean_state(tmp_path):
    """Computing a transition without committing it must not corrupt the DB."""
    db = SQLiteRunStore(tmp_path / "pre.db")
    db.create_run("r", config={}, status="running")
    rt = _make_runtime()

    # Simulate: process crashes right after cycle() but before apply_cycle_transition()
    transition = rt.cycle("r", {"text": "crash-before-commit"})

    # No commit — state in SQLite should still be at cycle_id == 0
    state = db.load_state("r")
    assert state.cycle_id == 0
    events = db.load_events("r")
    assert events == [], "No events must appear if transition was never committed"


# ---------------------------------------------------------------------------
# Scenario 2: commit succeeds; process "crashes" before SSE fan-out
# ---------------------------------------------------------------------------

def test_post_commit_crash_state_and_events_consistent(tmp_path):
    """Even if SSE fan-out never happens, state and events must be consistent."""
    db = SQLiteRunStore(tmp_path / "post.db")
    db.create_run("r", config={}, status="running")
    rt = _make_runtime()

    transition = rt.cycle("r", {"text": "commit-then-crash"})
    db.apply_cycle_transition(transition)  # commit atomically

    # Simulate crash: skip SSE fan-out entirely

    # After "restart": verify alignment
    state = db.load_state("r")
    events = db.load_events("r")

    assert state.cycle_id == 1
    cycle_events = [e for e in events if e["type"] == "cycle_completed"]
    assert len(cycle_events) == 1
    assert cycle_events[0]["payload"]["cycle_id"] == state.cycle_id


# ---------------------------------------------------------------------------
# Scenario 3: multiple cycles, then reload — state.cycle_id must match committed cycles
# ---------------------------------------------------------------------------

def test_state_cycle_id_matches_commit_count(tmp_path):
    db = SQLiteRunStore(tmp_path / "multi.db")
    db.create_run("r", config={}, status="running")
    rt = _make_runtime()

    n = 5
    for _ in range(n):
        t = rt.cycle("r", {})
        db.apply_cycle_transition(t)

    state = db.load_state("r")
    assert state.cycle_id == n

    cycle_events = [e for e in db.load_events("r") if e["type"] == "cycle_completed"]
    assert len(cycle_events) == n

    # State cycle_id == number of committed cycles
    committed_cycle_ids = sorted(e["payload"]["cycle_id"] for e in cycle_events)
    assert committed_cycle_ids == list(range(1, n + 1))


# ---------------------------------------------------------------------------
# Scenario 4: supervisor restart restores both state and event stream
# ---------------------------------------------------------------------------

async def _run_then_restart(db_path):
    scheduler, db, _ = _make_scheduler(db_path)
    sv = await scheduler.create_run(
        "restart_run",
        RunConfig(tick_interval_sec=0.02, idle_enabled=True),
        {"text": "initial"},
    )
    await asyncio.sleep(0.12)
    await sv.stop()

    cycles_before = db.load_state("restart_run").cycle_id
    events_before = db.load_events("restart_run")

    # Restart: new scheduler, same DB
    scheduler2, db2, _ = _make_scheduler(db_path)
    await scheduler2.recover_runs()

    # State must be intact after recovery
    state_after = db2.load_state("restart_run")
    events_after = db2.load_events("restart_run")

    return cycles_before, events_before, state_after, events_after


def test_supervisor_restart_preserves_alignment(tmp_path):
    c_before, ev_before, state_after, ev_after = asyncio.run(
        _run_then_restart(tmp_path / "sv.db")
    )
    assert state_after.cycle_id >= c_before
    # New events may have been added by recovered run, but old events still present
    seqs_before = {e["seq"] for e in ev_before}
    seqs_after = {e["seq"] for e in ev_after}
    assert seqs_before.issubset(seqs_after), "Old events must not disappear after restart"


# ---------------------------------------------------------------------------
# Scenario 5: events are strictly monotonic; no orphan events
# ---------------------------------------------------------------------------

def test_no_orphan_events_across_restarts(tmp_path):
    db = SQLiteRunStore(tmp_path / "orphan.db")
    db.create_run("r", config={}, status="running")
    rt = _make_runtime()

    # Commit 3 real cycles
    for _ in range(3):
        t = rt.cycle("r", {})
        db.apply_cycle_transition(t)

    # Simulate: 2 more cycles computed but NOT committed (pre-commit crash)
    rt.cycle("r", {})
    rt.cycle("r", {})

    # State should reflect 3, not 5
    state = db.load_state("r")
    assert state.cycle_id == 3

    events = db.load_events("r")
    completed = [e for e in events if e["type"] == "cycle_completed"]
    assert len(completed) == 3

    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs), "no duplicate seqs"
