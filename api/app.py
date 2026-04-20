from __future__ import annotations

from fastapi import FastAPI

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.api.routes import build_router
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore


class DBAdapter:
    def __init__(self, db: SQLiteRunStore) -> None:
        self.db = db

    def load(self, run_id: str):
        state = self.db.load_state(run_id)
        if state is None:
            self.db.create_run(run_id, config={}, status='running')
            state = self.db.load_state(run_id)
        return state

    def save(self, run_id: str, state) -> None:
        self.db.save_state(run_id, state)


def create_app(db_path: str = 'runtime.db') -> FastAPI:
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())
    memory_sink: list[dict] = []
    registry = build_tool_registry(memory_sink=memory_sink, allowed_roots=['.'])

    def runtime_factory() -> RuntimeCore:
        return RuntimeCore(
            state_store=DBAdapter(db),
            gate=ActionGate(registry),
            executor=Executor(registry),
        )

    scheduler = RuntimeScheduler(runtime_factory=runtime_factory, events=events, db=db)
    app = FastAPI(title='subjective_runtime_v2_1 phase2')
    app.include_router(build_router(runtime_factory, scheduler, db, events))

    @app.on_event('startup')
    async def _startup_recover() -> None:
        await scheduler.recover_runs()

    app.state.scheduler = scheduler
    app.state.db = db
    app.state.events = events
    return app


app = create_app()
