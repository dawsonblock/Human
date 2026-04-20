from __future__ import annotations

from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.runtime.supervisor import RunConfig


class RuntimeService:
    def __init__(self, scheduler: RuntimeScheduler) -> None:
        self.scheduler = scheduler

    async def create_run(self, run_id: str, config: RunConfig, initial_inputs: dict | None = None):
        return await self.scheduler.create_run(run_id, config, initial_inputs)

    async def inject_input(self, run_id: str, inputs: dict) -> None:
        supervisor = self.scheduler.get(run_id)
        if supervisor is None:
            raise KeyError(f'run not found: {run_id}')
        await supervisor.inject_input(inputs)
