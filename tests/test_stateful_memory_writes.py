"""Tests for stateful memory_write: writes mutate persisted agent state.

Acceptance criterion: a memory_write action changes persisted runtime state
and influences later cycles. The effect must be visible after reload, not only
in-process.
"""
from __future__ import annotations

import asyncio

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall
from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.runtime.supervisor import RunConfig
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def _registry():
    return build_tool_registry(allowed_roots=["."])


# ---------------------------------------------------------------------------
# MemoryWriteTool unit-level
# ---------------------------------------------------------------------------

def test_memory_write_working_note_routes_to_working_memory():
    registry = _registry()
    result = registry.invoke(
        ToolCall(tool_name="memory_write", arguments={"kind": "working_note", "payload": {"note": "hello"}}, reason="test"),
        ExecutionContext("r", 1, False, {}, {}, {}, {}),
    )
    assert result.ok is True
    assert len(result.memory_writes) == 1
    assert result.memory_writes[0]["kind"] == "working_note"


def test_memory_write_episode_routes_correctly():
    registry = _registry()
    result = registry.invoke(
        ToolCall(tool_name="memory_write", arguments={"kind": "episode", "payload": {"summary": "step 1"}}, reason="test"),
        ExecutionContext("r", 2, False, {}, {}, {}, {}),
    )
    assert result.ok is True
    assert result.memory_writes[0]["kind"] == "episode"


def test_memory_write_self_history_routes_correctly():
    registry = _registry()
    result = registry.invoke(
        ToolCall(tool_name="memory_write", arguments={"kind": "self_history", "payload": {"event": "learned"}}, reason="test"),
        ExecutionContext("r", 3, False, {}, {}, {}, {}),
    )
    assert result.ok is True
    assert result.memory_writes[0]["kind"] == "self_history"


def test_memory_write_unknown_kind_returns_error():
    registry = _registry()
    result = registry.invoke(
        ToolCall(tool_name="memory_write", arguments={"kind": "bogus", "payload": {}}, reason="test"),
        ExecutionContext("r", 1, False, {}, {}, {}, {}),
    )
    assert result.ok is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# Core integration: memory_writes applied to state
# ---------------------------------------------------------------------------

def test_working_note_written_to_working_memory_in_state():
    """memory_write working_note → state.working_memory after _apply_tool_mutations."""
    runtime = RuntimeCore(InMemoryStateStore(), ActionGate(_registry()), Executor(_registry()))
    state = AgentStateV2_1()

    outcome = {
        "status": "ok",
        "tool_name": "memory_write",
        "arguments": {},
        "result": {"written": True},
        "error": None,
        "latency_ms": 1.0,
        "memory_writes": [{"kind": "working_note", "payload": {"note": "test"}, "cycle_id": 1}],
        "state_delta": {},
        "observations": [],
    }

    runtime._apply_tool_mutations(state, outcome)
    assert any(w.get("kind") == "working_note" for w in state.working_memory)


def test_episode_written_to_episodic_trace():
    runtime = RuntimeCore(InMemoryStateStore(), ActionGate(_registry()), Executor(_registry()))
    state = AgentStateV2_1()

    outcome = {
        "status": "ok",
        "tool_name": "memory_write",
        "arguments": {},
        "result": {"written": True},
        "error": None,
        "latency_ms": 1.0,
        "memory_writes": [{"kind": "episode", "payload": {"summary": "ep1"}, "cycle_id": 1}],
        "state_delta": {},
        "observations": [],
    }

    runtime._apply_tool_mutations(state, outcome)
    assert any(w.get("kind") == "episode" for w in state.episodic_trace)


def test_self_history_written_to_self_history():
    runtime = RuntimeCore(InMemoryStateStore(), ActionGate(_registry()), Executor(_registry()))
    state = AgentStateV2_1()

    outcome = {
        "status": "ok",
        "memory_writes": [{"kind": "self_history", "payload": {"event": "ev1"}, "cycle_id": 1}],
        "state_delta": {},
        "observations": [],
    }

    runtime._apply_tool_mutations(state, outcome)
    assert any(w.get("kind") == "self_history" for w in state.self_history)


# ---------------------------------------------------------------------------
# Persistence: memory write survives DB round-trip
# ---------------------------------------------------------------------------

async def _run_memory_write_and_reload(db_path):
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())

    def runtime_factory():
        return RuntimeCore(InMemoryStateStore(), ActionGate(_registry()), Executor(_registry()))

    # Create run and get to a state where memory_write is executed
    scheduler = RuntimeScheduler(runtime_factory, events, db)
    supervisor = await scheduler.create_run("mw1", RunConfig(tick_interval_sec=0.02), {})

    # Inject a manual working_note via the runtime's mutation path
    await asyncio.sleep(0.05)
    state = db.load_state("mw1")
    outcome = {
        "status": "ok",
        "memory_writes": [{"kind": "working_note", "payload": {"note": "persisted_note"}, "cycle_id": state.cycle_id}],
        "state_delta": {},
        "observations": [],
    }
    supervisor.runtime._apply_tool_mutations(state, outcome)
    db.save_state("mw1", state)

    await supervisor.stop()

    # Reload from DB and check persistence
    reloaded = db.load_state("mw1")
    return reloaded


def test_memory_write_persists_across_reload(tmp_path):
    state = asyncio.run(_run_memory_write_and_reload(tmp_path / "runtime.db"))
    notes = [w for w in state.working_memory if w.get("kind") == "working_note"]
    assert any(n["payload"].get("note") == "persisted_note" for n in notes)
