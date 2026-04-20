import asyncio

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.runtime.supervisor import RunConfig
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore


async def _exercise(db_path):
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())
    registry = build_tool_registry(memory_sink=[], allowed_roots=['.'])

    class DBAdapter:
        def load(self, run_id):
            state = db.load_state(run_id)
            if state is None:
                db.create_run(run_id, config={}, status='running')
                state = db.load_state(run_id)
            return state
        def save(self, run_id, state):
            db.save_state(run_id, state)

    def runtime_factory():
        return RuntimeCore(DBAdapter(), ActionGate(registry), Executor(registry))

    scheduler = RuntimeScheduler(runtime_factory, events, db)
    supervisor = await scheduler.create_run('recover_me', RunConfig(tick_interval_sec=0.05), {'text': 'hello'})
    await asyncio.sleep(0.12)
    await supervisor.pause()
    assert db.get_run('recover_me').status == 'paused'

    scheduler2 = RuntimeScheduler(runtime_factory, events, db)
    await scheduler2.recover_runs()
    recovered = scheduler2.get('recover_me')
    assert recovered is not None
    assert recovered.is_paused
    await recovered.stop()


def test_supervisor_recovery(tmp_path):
    asyncio.run(_exercise(tmp_path / 'runtime.db'))
