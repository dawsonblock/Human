"""Supervisor recovery tests: persisted runs restart correctly after simulated crash.

Acceptance criterion from the problem statement:
  - supervisor recovery from persisted running and paused runs
  - state preserved across restart
  - events durable across restart
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


def _make_scheduler(db_path):
    db = SQLiteRunStore(db_path)
    em = EventManager(db, LiveEventBus())
    registry = build_tool_registry(allowed_roots=["."])

    def runtime_factory():
        # Use InMemoryStateStore — the supervisor seeds it from SQLite on start()
        # and commits atomically via apply_cycle_transition() each cycle.
        return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))

    return RuntimeScheduler(runtime_factory, em, db), db, em


async def _exercise_paused_recovery(db_path):
    scheduler, db, _ = _make_scheduler(db_path)

    supervisor = await scheduler.create_run(
        "paused_recover",
        RunConfig(tick_interval_sec=0.02, idle_enabled=True),
        {"text": "start"},
    )
    await asyncio.sleep(0.12)
    await supervisor.pause()

    state_before = db.load_state("paused_recover")
    cycle_before = state_before.cycle_id if state_before else 0
    assert db.get_run("paused_recover").status == "paused"

    # Simulate process restart with a fresh scheduler on same DB
    scheduler2, db2, _ = _make_scheduler(db_path)
    await scheduler2.recover_runs()

    recovered = scheduler2.get("paused_recover")
    assert recovered is not None
    assert recovered.is_paused

    state_after = db2.load_state("paused_recover")
    assert state_after.cycle_id >= cycle_before

    await recovered.stop()


def test_paused_run_recovers(tmp_path):
    asyncio.run(_exercise_paused_recovery(tmp_path / "paused.db"))


async def _exercise_running_recovery(db_path):
    scheduler, db, _ = _make_scheduler(db_path)

    supervisor = await scheduler.create_run(
        "running_recover",
        RunConfig(tick_interval_sec=0.03, idle_enabled=True),
    )
    await asyncio.sleep(0.1)

    # Simulate crash: don't stop cleanly. Status is still "running" in DB.
    assert db.get_run("running_recover").status == "running"

    scheduler2, db2, _ = _make_scheduler(db_path)
    await scheduler2.recover_runs()

    recovered = scheduler2.get("running_recover")
    assert recovered is not None
    assert recovered.is_running

    await recovered.stop()


def test_running_run_recovers(tmp_path):
    asyncio.run(_exercise_running_recovery(tmp_path / "running.db"))


async def _exercise_events_survive_restart(db_path):
    scheduler, db, _ = _make_scheduler(db_path)

    supervisor = await scheduler.create_run(
        "event_persist",
        RunConfig(tick_interval_sec=0.02),
        {"text": "hello"},
    )
    await asyncio.sleep(0.15)
    await supervisor.stop()

    events_before = db.load_events("event_persist")
    assert len(events_before) > 0
    seqs_before = [e["seq"] for e in events_before]
    assert seqs_before == list(range(1, len(seqs_before) + 1))

    # Second scheduler (fresh process) reads the same events
    _, db2, _ = _make_scheduler(db_path)
    events_after = db2.load_events("event_persist")
    assert len(events_after) == len(events_before)
    assert [e["seq"] for e in events_after] == seqs_before


def test_events_survive_restart(tmp_path):
    asyncio.run(_exercise_events_survive_restart(tmp_path / "events.db"))



async def _exercise_paused_recovery(db_path):
    scheduler, db, _ = _make_scheduler(db_path)

    supervisor = await scheduler.create_run(
        "paused_recover",
        RunConfig(tick_interval_sec=0.02, idle_enabled=True),
        {"text": "start"},
    )
    await asyncio.sleep(0.12)
    await supervisor.pause()

    state_before = db.load_state("paused_recover")
    cycle_before = state_before.cycle_id if state_before else 0
    assert db.get_run("paused_recover").status == "paused"

    # Simulate process restart with a fresh scheduler on same DB
    scheduler2, db2, _ = _make_scheduler(db_path)
    await scheduler2.recover_runs()

    recovered = scheduler2.get("paused_recover")
    assert recovered is not None
    assert recovered.is_paused

    state_after = db2.load_state("paused_recover")
    assert state_after.cycle_id >= cycle_before

    await recovered.stop()


def test_paused_run_recovers(tmp_path):
    asyncio.run(_exercise_paused_recovery(tmp_path / "paused.db"))


async def _exercise_running_recovery(db_path):
    scheduler, db, _ = _make_scheduler(db_path)

    supervisor = await scheduler.create_run(
        "running_recover",
        RunConfig(tick_interval_sec=0.03, idle_enabled=True),
    )
    await asyncio.sleep(0.1)

    # Simulate crash: don't stop cleanly. Status is still "running" in DB.
    assert db.get_run("running_recover").status == "running"

    scheduler2, db2, _ = _make_scheduler(db_path)
    await scheduler2.recover_runs()

    recovered = scheduler2.get("running_recover")
    assert recovered is not None
    assert recovered.is_running

    await recovered.stop()


def test_running_run_recovers(tmp_path):
    asyncio.run(_exercise_running_recovery(tmp_path / "running.db"))


async def _exercise_events_survive_restart(db_path):
    scheduler, db, _ = _make_scheduler(db_path)

    supervisor = await scheduler.create_run(
        "event_persist",
        RunConfig(tick_interval_sec=0.02),
        {"text": "hello"},
    )
    await asyncio.sleep(0.15)
    await supervisor.stop()

    events_before = db.load_events("event_persist")
    assert len(events_before) > 0
    seqs_before = [e["seq"] for e in events_before]
    assert seqs_before == list(range(1, len(seqs_before) + 1))

    # Second scheduler (fresh process) reads the same events
    _, db2, _ = _make_scheduler(db_path)
    events_after = db2.load_events("event_persist")
    assert len(events_after) == len(events_before)
    assert [e["seq"] for e in events_after] == seqs_before


def test_events_survive_restart(tmp_path):
    asyncio.run(_exercise_events_survive_restart(tmp_path / "events.db"))
