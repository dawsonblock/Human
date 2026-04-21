"""Regression test: recovered paused runs resume and continue cycling.

Before the fix, recovering a paused run set supervisor._paused = True but
never created the loop task.  Calling resume() only flipped the flag; the
cycle counter never advanced.

After the fix, recover_runs() creates the task (paused), and resume() lets the
loop proceed normally.
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


def _make_factory(registry):
    def factory():
        return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))
    return factory


async def _exercise(db_path):
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())
    registry = build_tool_registry(allowed_roots=['.'])
    factory = _make_factory(registry)

    # --- Phase 1: start a run, let it cycle, pause it ---
    scheduler1 = RuntimeScheduler(factory, events, db)
    supervisor1 = await scheduler1.create_run(
        'paused_resume_test',
        RunConfig(tick_interval_sec=0.05),
        {'text': 'initial'},
    )
    await asyncio.sleep(0.15)  # let a few cycles run
    await supervisor1.pause()

    state_before = db.load_state('paused_resume_test')
    cycle_at_pause = state_before.cycle_id
    assert cycle_at_pause > 0, "should have cycled before pause"
    assert db.get_run('paused_resume_test').status == 'paused'

    # --- Phase 2: recover into a new scheduler ---
    scheduler2 = RuntimeScheduler(factory, events, db)
    await scheduler2.recover_runs()
    recovered = scheduler2.get('paused_resume_test')
    assert recovered is not None, "run must be present in new scheduler"
    assert recovered.is_paused, "recovered run must be paused"

    # The loop task must exist (created during recovery) even though it is paused.
    assert recovered._task is not None, "loop task must be created on recovery"
    assert not recovered._task.done(), "loop task must be alive"

    # Cycle counter must NOT advance while paused.
    await asyncio.sleep(0.15)
    state_still_paused = db.load_state('paused_resume_test')
    assert state_still_paused.cycle_id == cycle_at_pause, (
        "cycle_id must not advance while paused"
    )

    # --- Phase 3: resume and verify cycles advance ---
    await recovered.resume()
    assert not recovered.is_paused
    await asyncio.sleep(0.20)  # give enough time for at least one new cycle

    state_after = db.load_state('paused_resume_test')
    assert state_after.cycle_id > cycle_at_pause, (
        f"cycle_id must advance after resume "
        f"(was {cycle_at_pause}, now {state_after.cycle_id})"
    )

    await recovered.stop()


def test_recovered_paused_run_resumes_and_cycles(tmp_path):
    asyncio.run(_exercise(tmp_path / 'runtime.db'))
