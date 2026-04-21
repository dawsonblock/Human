from __future__ import annotations

import asyncio
from dataclasses import asdict

from subjective_runtime_v2_1.runtime.events import EventManager
from subjective_runtime_v2_1.runtime.supervisor import RunConfig, RunSupervisor
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore


class RuntimeScheduler:
    def __init__(self, runtime_factory, events: EventManager, db: SQLiteRunStore) -> None:
        self.runtime_factory = runtime_factory
        self.events = events
        self.db = db
        self.supervisors: dict[str, RunSupervisor] = {}

    async def create_run(self, run_id: str, config: RunConfig, initial_inputs: dict | None = None) -> RunSupervisor:
        if not self.db.has_run(run_id):
            self.db.create_run(run_id, config=asdict(config), state=AgentStateV2_1(), status='running')
        supervisor = RunSupervisor(
            run_id=run_id,
            runtime=self.runtime_factory(),
            events=self.events,
            config=config,
            run_store=self.db,
        )
        self.supervisors[run_id] = supervisor
        await supervisor.start(initial_inputs=initial_inputs)
        return supervisor

    def get(self, run_id: str) -> RunSupervisor | None:
        return self.supervisors.get(run_id)

    async def stop_run(self, run_id: str) -> None:
        supervisor = self.supervisors.get(run_id)
        if supervisor is not None:
            await supervisor.stop()
            del self.supervisors[run_id]

    async def recover_runs(self) -> None:
        for meta in self.db.list_recoverable_runs():
            if meta.run_id in self.supervisors:
                continue
            supervisor = RunSupervisor(
                run_id=meta.run_id,
                runtime=self.runtime_factory(),
                events=self.events,
                config=RunConfig(**meta.config),
                run_store=self.db,
            )
            self.supervisors[meta.run_id] = supervisor
            if meta.status == 'running':
                await supervisor.start()
            elif meta.status == 'paused':
                # Seed the runtime's in-memory store from SQLite so the first
                # cycle after resume sees the correct prior state.
                state = self.db.load_state(meta.run_id)
                if state is not None:
                    supervisor.runtime.state_store.save(meta.run_id, state)
                # Start the loop task in paused state so that calling resume()
                # is sufficient to restart execution without any extra wiring.
                supervisor._paused = True
                supervisor._task = asyncio.create_task(supervisor._run_loop())
