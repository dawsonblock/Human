"""FastAPI application factory for the Human Runtime.

Configuration is resolved in priority order:
  1. Explicit keyword arguments to ``create_app()``
  2. Environment variables (``HUMAN_DATA_DIR``, ``HUMAN_DB_PATH``, ``HUMAN_ALLOWED_ROOTS``)
  3. Defaults (``./data/runtime.db``, ``./data/workspace``)

See ``storage/paths.py`` for full env var documentation.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.api.routes import build_router, build_dev_router
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.storage.paths import StoragePaths
from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend
from subjective_runtime_v2_1.state.store import InMemoryStateStore

_STATIC_DIR = Path(__file__).parent / 'static'


class StateSeeder:
    """Loads initial state from SQLite to seed RuntimeCore's in-memory buffer.

    ``save()`` raises ``NotImplementedError`` to make it obvious that
    RuntimeCore must not directly persist state.  The supervisor is the sole
    authority for committing state+events via
    ``SQLiteRunStore.apply_cycle_transition()``.
    """
    def __init__(self, db: SQLiteBackend) -> None:
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


def create_app(
    db_path: str | None = None,
    allowed_roots: list[str] | None = None,
) -> FastAPI:
    """Create and configure the Human Runtime FastAPI application.

    Parameters
    ----------
    db_path:
        Explicit SQLite database path.  If ``None``, resolved from
        ``HUMAN_DB_PATH`` env var or ``{HUMAN_DATA_DIR}/runtime.db``.
    allowed_roots:
        Explicit list of allowed tool root directories.  If ``None``,
        resolved from ``HUMAN_ALLOWED_ROOTS`` env var or a default
        workspace directory inside the data dir.
    """
    # Resolve paths from env vars / defaults
    paths = StoragePaths(
        db_path=db_path,
        allowed_roots=allowed_roots,
    )
    paths.ensure_data_dir()

    db = SQLiteBackend(paths.db_path)
    roots = paths.allowed_roots_str
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
        db.close()

    app = FastAPI(title='subjective_runtime_v2_1', lifespan=lifespan)
    app.include_router(build_router(runtime_factory, scheduler, db, events, registry), prefix="/api")

    import os
    if os.getenv("ALLOW_DEV_TERMINAL") == "1":
        app.include_router(build_dev_router(), prefix="/api")

    # Serve the single-page UI
    if _STATIC_DIR.exists():
        app.mount('/static', StaticFiles(directory=str(_STATIC_DIR)), name='static')

        @app.get('/', include_in_schema=False)
        async def serve_ui():
            return FileResponse(str(_STATIC_DIR / 'index.html'))

    app.state.scheduler = scheduler
    app.state.db = db
    app.state.events = events
    app.state.paths = paths
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("subjective_runtime_v2_1.api.app:app", host="0.0.0.0", port=8000, reload=True)
