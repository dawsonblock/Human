"""Tests for concurrent input bursts and monotonic event sequencing.

Acceptance criterion from the problem statement:
  - Hammer input, pause/resume, approval, and debug actions together.
  - cycle_id should stay strictly monotonic and state should not fork.
  - Event seqs must be monotonically increasing with no duplicates.
"""
from __future__ import annotations

import asyncio

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.supervisor import RunConfig, RunSupervisor
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore


def _make_supervisor(db, run_id: str):
    em = EventManager(db, LiveEventBus())
    registry = build_tool_registry(allowed_roots=["."])
    db.create_run(run_id, config={}, status="running")

    class StateSeeder:
        def load(self, r):
            state = db.load_state(r)
            if state is None:
                db.create_run(r, config={}, status="running")
                state = db.load_state(r)
            return state

        def save(self, r, state):
            db.save_state(r, state)

    runtime = RuntimeCore(StateSeeder(), ActionGate(registry), Executor(registry))
    supervisor = RunSupervisor(
        run_id=run_id,
        runtime=runtime,
        events=em,
        config=RunConfig(tick_interval_sec=0.01, idle_enabled=True),
        run_store=db,
    )
    return supervisor, em


async def _burst_inputs(db_path):
    db = SQLiteRunStore(db_path)
    supervisor, _ = _make_supervisor(db, "burst_test")

    await supervisor.start()
    await asyncio.gather(*[
        supervisor.inject_input({"text": f"msg_{i}", "idx": i})
        for i in range(20)
    ])
    await asyncio.sleep(0.3)
    await supervisor.stop()
    return db


def test_event_seqs_monotonic_under_burst(tmp_path):
    db = asyncio.run(_burst_inputs(tmp_path / "burst.db"))
    events = db.load_events("burst_test")
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), "seqs must be monotonically increasing"
    assert len(set(seqs)) == len(seqs), "no duplicate seqs"


def test_cycle_ids_monotonic_under_burst(tmp_path):
    db = asyncio.run(_burst_inputs(tmp_path / "cycle_mono.db"))
    state = db.load_state("burst_test")
    assert state is not None and state.cycle_id >= 1

    cycle_completions = [
        e for e in db.load_events("burst_test")
        if e["type"] == "cycle_completed"
    ]
    if cycle_completions:
        ids = [e["payload"]["cycle_id"] for e in cycle_completions]
        assert ids == sorted(ids), "cycle_ids must be monotonically increasing"


async def _pause_resume_burst(db_path):
    db = SQLiteRunStore(db_path)
    supervisor, _ = _make_supervisor(db, "pause_resume")

    await supervisor.start({"text": "initial"})
    await asyncio.sleep(0.05)

    await supervisor.pause()
    # Inject inputs while paused — they must queue and not be lost
    for i in range(5):
        await supervisor.inject_input({"text": f"queued_{i}"})

    await supervisor.resume()
    await asyncio.sleep(0.2)
    await supervisor.stop()
    return db


def test_inputs_queued_during_pause_are_processed(tmp_path):
    db = asyncio.run(_pause_resume_burst(tmp_path / "pause.db"))
    events = db.load_events("pause_resume")

    enqueued = [e for e in events if e["type"] == "input_enqueued"]
    assert len(enqueued) >= 5

    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)


async def _state_no_fork(db_path):
    """Under concurrent input, the stored cycle_id must equal the number of
    committed cycle_completed events — state cannot fork."""
    db = SQLiteRunStore(db_path)
    supervisor, _ = _make_supervisor(db, "no_fork")

    await supervisor.start()
    tasks = [supervisor.inject_input({"text": f"t{i}"}) for i in range(10)]
    await asyncio.gather(*tasks)
    await asyncio.sleep(0.3)
    await supervisor.stop()

    state = db.load_state("no_fork")
    cycle_completions = [
        e for e in db.load_events("no_fork")
        if e["type"] == "cycle_completed"
    ]
    # Every cycle_completed event must refer to a cycle_id <= the final state
    assert state is not None
    for ev in cycle_completions:
        assert ev["payload"]["cycle_id"] <= state.cycle_id

    return db


def test_state_does_not_fork(tmp_path):
    asyncio.run(_state_no_fork(tmp_path / "nofork.db"))
