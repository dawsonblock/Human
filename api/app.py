from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.api.routes import build_router
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore

_STATIC_DIR = Path(__file__).parent / 'static'


class StateSeeder:
    """Loads initial state from SQLite to seed RuntimeCore's in-memory buffer.

    ``save()`` raises ``NotImplementedError`` to make it obvious that
    RuntimeCore must not directly persist state.  The supervisor is the sole
    authority for committing state+events via
    ``SQLiteRunStore.apply_cycle_transition()``.
    """
    def __init__(self, db: SQLiteRunStore) -> None:
        self.db = db

    def load(self, run_id: str):
        state = self.db.load_state(run_id)
        if state is None:
            self.db.create_run(run_id, config={}, status='running')
            state = self.db.load_state(run_id)
        return state

    def save(self, run_id: str, state) -> None:
        raise NotImplementedError(
            "StateSeeder.save() must not be called directly. "
            "Use SQLiteRunStore.apply_cycle_transition() to persist state atomically."
        )


def create_app(db_path: str = 'runtime.db', allowed_roots: list[str] | None = None) -> FastAPI:
    roots = allowed_roots or ['.']
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())
    registry = build_tool_registry(allowed_roots=roots)

    def runtime_factory() -> RuntimeCore:
        # Each supervisor gets its own RuntimeCore with a private InMemoryStateStore.
        # The supervisor seeds the store from SQLite on start().
        return RuntimeCore(
            state_store=InMemoryStateStore(),
            gate=ActionGate(registry),
            executor=Executor(registry),
            allowed_roots=roots,
        )

    scheduler = RuntimeScheduler(runtime_factory=runtime_factory, events=events, db=db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await scheduler.recover_runs()
        yield

    app = FastAPI(title='subjective_runtime_v2_1', lifespan=lifespan)
    app.include_router(build_router(runtime_factory, scheduler, db, events, registry))

    # Serve the single-page UI
    if _STATIC_DIR.exists():
        app.mount('/static', StaticFiles(directory=str(_STATIC_DIR)), name='static')

        @app.get('/', include_in_schema=False)
        async def serve_ui():
            return FileResponse(str(_STATIC_DIR / 'index.html'))

    app.state.scheduler = scheduler
    app.state.db = db
    app.state.events = events
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("subjective_runtime_v2_1.api.app:app", host="0.0.0.0", port=8000, reload=True)
