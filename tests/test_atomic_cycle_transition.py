"""Test that one cycle commits both state and events atomically.

Acceptance criterion: the store must never show new cycle events without
the matching state.cycle_id, and vice-versa.
"""
from __future__ import annotations

import pytest

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def _make_runtime():
    reg = build_tool_registry(allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(reg), Executor(reg))


def test_transition_object_is_returned(tmp_path):
    """cycle() must return a CycleTransition, not the old CycleResult dict."""
    rt = _make_runtime()
    result = rt.cycle("r", {"text": "hello"})
    assert isinstance(result, CycleTransition)


def test_events_are_runtime_event_drafts(tmp_path):
    """CycleTransition.events must be RuntimeEventDraft objects, not raw tuples."""
    rt = _make_runtime()
    result = rt.cycle("r", {"text": "hello"})
    assert all(isinstance(e, RuntimeEventDraft) for e in result.events)


def test_cycle_id_matches_state(tmp_path):
    rt = _make_runtime()
    result = rt.cycle("r", {"text": "hello"})
    assert result.cycle_id == result.state.cycle_id


def test_new_state_alias(tmp_path):
    """CycleTransition.new_state must be a backward-compat alias for .state."""
    rt = _make_runtime()
    result = rt.cycle("r", {"text": "hello"})
    assert result.new_state is result.state


def test_apply_cycle_transition_with_transition_object(tmp_path):
    """apply_cycle_transition(transition) commits state+events atomically."""
    db = SQLiteRunStore(tmp_path / "t.db")
    db.create_run("r1", config={}, status="running")
    rt = _make_runtime()
    transition = rt.cycle("r1", {"text": "hi"})

    committed = db.apply_cycle_transition(transition)

    # State committed
    state = db.load_state("r1")
    assert state.cycle_id == transition.cycle_id

    # Events committed with correct count
    assert len(committed) == len(transition.events)
    events = db.load_events("r1")
    assert len(events) == len(transition.events)


def test_state_and_events_never_diverge(tmp_path):
    """After apply_cycle_transition, every committed event refers to the current cycle_id."""
    db = SQLiteRunStore(tmp_path / "nd.db")
    db.create_run("r2", config={}, status="running")
    rt = _make_runtime()

    for _ in range(3):
        t = rt.cycle("r2", {})
        db.apply_cycle_transition(t)

    state = db.load_state("r2")
    events = db.load_events("r2")
    cycle_events = [e for e in events if e["type"] == "cycle_completed"]

    # Every cycle_completed refers to a cycle_id <= the final committed state
    for ev in cycle_events:
        assert ev["payload"]["cycle_id"] <= state.cycle_id

    # Final state cycle_id equals number of cycles
    assert state.cycle_id == 3


def test_no_orphan_events_if_transition_never_called(tmp_path):
    """If apply_cycle_transition is never called, no events appear in the DB."""
    db = SQLiteRunStore(tmp_path / "no_orphan.db")
    db.create_run("r3", config={}, status="running")
    rt = _make_runtime()

    # Run a cycle but deliberately do NOT commit the transition
    _ = rt.cycle("r3", {"text": "orphan"})

    events = db.load_events("r3")
    assert events == [], "events should be empty when transition is not committed"

    state = db.load_state("r3")
    assert state.cycle_id == 0, "SQLite state should still be at cycle 0"


def test_seq_strictly_monotonic_across_multiple_transitions(tmp_path):
    db = SQLiteRunStore(tmp_path / "seq.db")
    db.create_run("r4", config={}, status="running")
    rt = _make_runtime()

    for _ in range(5):
        t = rt.cycle("r4", {})
        db.apply_cycle_transition(t)

    events = db.load_events("r4")
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(1, len(seqs) + 1)), "seqs must be strictly monotonic"
